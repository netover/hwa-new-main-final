"""
SQLite based Job Queue for RAG Microservice

This module implements a persistent and reliable job queue using SQLite
as a fallback when Redis Streams is not available (e.g., Redis 3.0). It provides
sequential processing with job status tracking, timeouts, and retry logic.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import threading

from resync.core.exceptions import FileProcessingError
from resync.settings import settings
from ..config import settings as rag_settings

logger = logging.getLogger(__name__)

# Job status constants
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_TIMEOUT = "timeout"
JOB_STATUS_RETRYING = "retrying"
JOB_STATUS_NOT_FOUND = "not_found"

class SQLiteJobQueue:
    """
    SQLite-based job queue for RAG processing.

    Features:
    - Persistent storage using SQLite
    - Sequential job processing
    - Job status tracking
    - Timeout handling
    - Retry logic
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the SQLite job queue.

        Args:
            db_path: Path to the SQLite database file (uses settings if not provided)
        """
        self.db_path = db_path or rag_settings.JOB_QUEUE_DB_PATH
        self.lock = threading.Lock()
        self.max_retries = getattr(settings, "rag_service_max_retries", 3)
        self.job_timeout_seconds = getattr(settings, "rag_service_timeout", 3600)
        self.retry_backoff = getattr(settings, "rag_service_retry_backoff", 1.0)
        self.init_database()
        logger.info(f"SQLiteJobQueue initialized with DB: {self.db_path}")

    def init_database(self) -> None:
        """Initialize the SQLite database schema."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS job_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT UNIQUE NOT NULL,
                        file_path TEXT NOT NULL,
                        original_filename TEXT,
                        status TEXT NOT NULL DEFAULT 'queued',
                        progress INTEGER DEFAULT 0,
                        message TEXT,
                        metadata TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        retries INTEGER DEFAULT 0,
                        timeout_at DATETIME
                    )
                """)

                # Create indexes for faster lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_job_queue_status ON job_queue(status)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_job_queue_timeout ON job_queue(timeout_at)
                """)
                conn.commit()
            logger.info("SQLite database schema initialized.")

    async def enqueue_job(self, job_id: str, file_path: str, original_filename: str, metadata: Optional[Dict] = None) -> str:
        """
        Adds a job to the queue.

        Args:
            job_id: Unique identifier for the job.
            file_path: Path to the file to be processed.
            original_filename: Original name of the file.
            metadata: Optional dictionary of additional metadata.

        Returns:
            The job_id of the enqueued job.
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO job_queue (job_id, file_path, original_filename, metadata, status, progress, message, timeout_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    file_path,
                    original_filename,
                    json.dumps(metadata) if metadata else None,
                    JOB_STATUS_QUEUED,
                    0,
                    "Job queued",
                    (datetime.now() + timedelta(seconds=self.job_timeout_seconds)).isoformat()
                ))
                conn.commit()
            logger.info(f"Job {job_id} enqueued.")
            return job_id

    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the next job from the queue for processing.
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('BEGIN IMMEDIATE')

                # Handle expired jobs
                self._handle_expired_processing_jobs(conn)

                # Get next queued job
                cursor = conn.execute("""
                    SELECT * FROM job_queue
                    WHERE status = ?
                    ORDER BY created_at ASC
                    LIMIT 1
                """, (JOB_STATUS_QUEUED,))
                row = cursor.fetchone()

                if row:
                    job_id = row[1]
                    conn.execute("""
                        UPDATE job_queue
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE job_id = ?
                    """, (JOB_STATUS_PROCESSING, job_id))
                    conn.commit()

                    col_names = [description[0] for description in cursor.description]
                    job = dict(zip(col_names, row))
                    job['metadata'] = json.loads(job['metadata']) if job['metadata'] else None
                    logger.info(f"Job {job_id} retrieved for processing.")
                    return job
                else:
                    conn.commit()
                    return None

    def _handle_expired_processing_jobs(self, conn: sqlite3.Connection):
        """Handle jobs that timed out during processing."""
        current_time = datetime.now().isoformat()
        expired_jobs = conn.execute("""
            SELECT job_id, retries FROM job_queue
            WHERE status = ? AND timeout_at < ?
        """, (JOB_STATUS_PROCESSING, current_time)).fetchall()

        for job_id, retries in expired_jobs:
            if retries < self.max_retries:
                conn.execute("""
                    UPDATE job_queue
                    SET status = ?, retries = ?, updated_at = CURRENT_TIMESTAMP,
                    message = ?
                    WHERE job_id = ?
                """, (JOB_STATUS_RETRYING, retries + 1, f"Job timed out, retrying (attempt {retries + 1}/{self.max_retries})", job_id))
                logger.warning(f"Job {job_id} timed out, marked for retry.")
            else:
                conn.execute("""
                    UPDATE job_queue
                    SET status = ?, updated_at = CURRENT_TIMESTAMP, message = ?
                    WHERE job_id = ?
                """, (JOB_STATUS_FAILED, "Job timed out and exceeded max retries", job_id))
                logger.error(f"Job {job_id} timed out and failed after max retries.")

    async def update_job_status(self, job_id: str, status: str, progress: Optional[int] = None, message: Optional[str] = None) -> bool:
        """Update job status."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                update_sql = """
                    UPDATE job_queue
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                """
                params = [status]

                if progress is not None:
                    update_sql += ", progress = ?"
                    params.append(progress)

                if message is not None:
                    update_sql += ", message = ?"
                    params.append(message)

                update_sql += " WHERE job_id = ?"
                params.append(job_id)

                cursor = conn.execute(update_sql, params)
                conn.commit()
                success = cursor.rowcount > 0
                if success:
                    logger.debug(f"Job {job_id} status updated to {status}.")
                return success

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("""
                    SELECT job_id, status, progress, message, retries, created_at, updated_at, timeout_at, original_filename, file_path
                    FROM job_queue
                    WHERE job_id = ?
                """, (job_id,)).fetchone()

                if row:
                    return dict(row)
                else:
                    return {
                        "job_id": job_id,
                        "status": JOB_STATUS_NOT_FOUND,
                        "progress": 0,
                        "message": "Job ID not found"
                    }

    async def cleanup_expired_jobs(self) -> int:
        """Clean up expired jobs."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                current_time = datetime.now().isoformat()
                cursor = conn.execute("""
                    SELECT job_id FROM job_queue
                    WHERE status IN (?, ?) AND timeout_at < ?
                """, (JOB_STATUS_QUEUED, JOB_STATUS_PROCESSING, current_time))
                expired_jobs = cursor.fetchall()

                if expired_jobs:
                    job_ids = [job[0] for job in expired_jobs]
                    conn.execute("""
                        UPDATE job_queue
                        SET status = ?, updated_at = CURRENT_TIMESTAMP, message = ?
                        WHERE job_id IN ({})
                    """.format(','.join('?' * len(job_ids))),
                    [JOB_STATUS_TIMEOUT, "Job timed out"] + job_ids)
                    conn.commit()
                    logger.info(f"Cleaned up {len(expired_jobs)} expired jobs.")
                    return len(expired_jobs)
                return 0

    async def get_pending_jobs_count(self) -> int:
        """Get count of pending jobs."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                count = conn.execute("""
                    SELECT COUNT(*) FROM job_queue
                    WHERE status IN (?, ?)
                """, (JOB_STATUS_QUEUED, JOB_STATUS_PROCESSING)).fetchone()[0]
                return count

    async def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM job_queue
                    ORDER BY created_at ASC
                """).fetchall()

                jobs = []
                for row in rows:
                    job = dict(row)
                    job['metadata'] = json.loads(job['metadata']) if job['metadata'] else None
                    jobs.append(job)
                return jobs


