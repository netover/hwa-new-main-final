"""
Redis-based Audit Queue for Resync

This module implements a scalable audit queue using Redis to replace SQLite.
The audit queue manages memories that need to be reviewed by administrators.
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from resync.core.audit_lock import DistributedAuditLock
from resync.core.exceptions import (
    AuditError,
    DatabaseError,
    DataParsingError,
    FileProcessingError,
)
from resync.core.structured_logger import get_logger
from resync.settings import settings

logger = get_logger(__name__)


class IAuditQueue(ABC):
    """
    Abstract interface for audit queue implementations.
    """

    @abstractmethod
    async def add_audit_record(self, memory: Dict[str, Any]) -> bool:
        """Add a new memory to the audit queue."""

    @abstractmethod
    async def get_pending_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending audit records."""

    @abstractmethod
    async def update_audit_status(self, memory_id: str, status: str) -> bool:
        """Update the status of an audit record."""

    @abstractmethod
    async def is_memory_approved(self, memory_id: str) -> bool:
        """Check if a memory has been approved."""

    @abstractmethod
    async def delete_audit_record(self, memory_id: str) -> bool:
        """Remove an audit record from the queue."""

    @abstractmethod
    async def get_queue_length(self) -> int:
        """Get the current length of the audit queue."""

    @abstractmethod
    async def cleanup_processed_audits(self, days_old: int = 30) -> int:
        """Remove old processed audits."""


class AsyncAuditQueue(IAuditQueue):
    """
    Redis-based audit queue for managing memories that need admin review.

    Uses Redis for high-performance, scalable operations with atomic operations
    and pub/sub capabilities for real-time updates.
    """

    def __init__(
        self, redis_url: Optional[str] = None, settings_module: Any = settings
    ):
        """
        Initialize the Redis-based audit queue.

        Args:
            redis_url: Redis connection URL. Defaults to environment variable or settings.
            settings_module: The settings module to use (default: global settings).
        """
        self.settings = settings_module
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL",
            (
                self.settings.REDIS_URL
                if hasattr(self.settings, "REDIS_URL")
                else "redis://localhost:6379"
            ),
        )
        # Implement connection pooling with settings configuration
        sync_pool = redis.ConnectionPool.from_url(
            self.redis_url,
            max_connections=getattr(self.settings, "REDIS_POOL_MAX_SIZE", 20),
            min_connections=getattr(self.settings, "REDIS_POOL_MIN_SIZE", 5),
            retry_on_timeout=True,
            health_check_interval=getattr(
                self.settings, "REDIS_POOL_HEALTH_CHECK_INTERVAL", 60
            ),
            socket_keepalive=True,
            socket_keepalive_options={},
            encoding="utf-8",
            decode_responses=False,
        )
        self.sync_client = redis.Redis(connection_pool=sync_pool)

        # Use async connection pool correctly
        from redis.asyncio import ConnectionPool as AsyncConnectionPool

        async_pool = AsyncConnectionPool.from_url(
            self.redis_url,
            max_connections=getattr(self.settings, "REDIS_POOL_MAX_SIZE", 20),
            min_connections=getattr(self.settings, "REDIS_POOL_MIN_SIZE", 5),
            retry_on_timeout=True,
            health_check_interval=getattr(
                self.settings, "REDIS_POOL_HEALTH_CHECK_INTERVAL", 60
            ),
            socket_keepalive=True,
            encoding="utf-8",
            decode_responses=False,
        )
        self.async_client = AsyncRedis(connection_pool=async_pool)

        # Use the new distributed audit lock for consistency
        self.distributed_lock = DistributedAuditLock(self.redis_url)

        # Redis keys
        self.audit_queue_key = "resync:audit_queue"
        self.audit_status_key = "resync:audit_status"  # Hash for memory_id -> status
        self.audit_data_key = "resync:audit_data"  # Hash for memory_id -> JSON data

        logger.info("async_audit_queue_initialized", redis_url=self.redis_url)

    async def add_audit_record(self, memory: Dict[str, Any]) -> bool:
        """
        Adds a new memory to the audit queue for review.

        Args:
            memory: Memory data to add to the queue.

        Returns:
            True if successfully added, False if already exists.
        """
        memory_id = memory["id"]

        # Check if already exists
        if await self.async_client.hexists(self.audit_status_key, memory_id):
            logger.warning("memory_already_exists_in_audit_queue", memory_id=memory_id)
            return False

        # Store memory data as JSON
        memory_data = {
            "memory_id": memory_id,
            "user_query": memory["user_query"],
            "agent_response": memory["agent_response"],
            "ia_audit_reason": memory.get("ia_audit_reason"),
            "ia_audit_confidence": memory.get("ia_audit_confidence"),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            async with self.async_client.pipeline() as pipe:
                # Add to queue (left push for FIFO)
                pipe.lpush(self.audit_queue_key, memory_id)
                # Store status
                pipe.hset(self.audit_status_key, memory_id, "pending")
                # Store data
                pipe.hset(self.audit_data_key, memory_id, json.dumps(memory_data))
                await pipe.execute()

            logger.info("added_memory_to_audit_queue", memory_id=memory_id)
            return True
        except RedisError as e:
            logger.error(
                "redis_error_while_adding_memory_to_audit_queue",
                memory_id=memory_id,
                error=str(e),
                exc_info=True,
            )
            # Consider this a critical error - raise exception to handle appropriately
            raise AuditError(
                f"Failed to add memory to audit queue due to Redis error: {e}"
            ) from e
        except TypeError as e:
            logger.error(
                "type_error_while_adding_memory_to_audit_queue",
                memory_id=memory_id,
                error=str(e),
                exc_info=True,
            )
            raise DataParsingError(
                f"Failed to serialize memory data for audit: {e}"
            ) from e
        except Exception as e:
            logger.error(
                "unexpected_error_while_adding_memory_to_audit_queue",
                memory_id=memory_id,
                error=str(e),
                exc_info=True,
            )
            raise AuditError(
                f"Failed to add memory to audit queue due to unexpected error: {e}"
            ) from e

    async def get_pending_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves pending audits from the queue.

        Args:
            limit: Maximum number of audits to return.

        Returns:
            List of pending audit records.
        """
        try:
            # Get memory IDs from queue
            memory_ids = await self.async_client.lrange(
                self.audit_queue_key, 0, limit - 1
            )

            if not memory_ids:
                return []

            # Get data for pending items only
            pending_audits = []
            for memory_id in memory_ids:
                memory_id_str = memory_id.decode("utf-8")
                status = await self.async_client.hget(
                    self.audit_status_key, memory_id_str
                )

                if status and status.decode("utf-8") == "pending":
                    data_json = await self.async_client.hget(
                        self.audit_data_key, memory_id_str
                    )
                    if data_json:
                        try:
                            data = json.loads(data_json.decode("utf-8"))
                            pending_audits.append(data)
                        except json.JSONDecodeError as e:
                            logger.error(
                                "failed_to_decode_json_for_memory",
                                memory_id=memory_id_str,
                                error=str(e),
                                exc_info=True,
                            )
                            # Continue processing other items instead of failing completely
                            continue
                        except UnicodeDecodeError as e:
                            logger.error(
                                "failed_to_decode_utf8_for_memory",
                                memory_id=memory_id_str,
                                error=str(e),
                                exc_info=True,
                            )
                            continue

            return pending_audits
        except RedisError as e:
            logger.error(
                "redis_error_while_retrieving_pending_audits",
                error=str(e),
                exc_info=True,
            )
            raise AuditError(
                f"Failed to retrieve pending audits due to Redis error: {e}"
            ) from e
        except Exception as e:
            logger.error(
                "unexpected_error_while_retrieving_pending_audits",
                error=str(e),
                exc_info=True,
            )
            raise AuditError(
                f"Failed to retrieve pending audits due to unexpected error: {e}"
            ) from e

    async def update_audit_status(self, memory_id: str, status: str) -> bool:
        """
        Updates the status of an audit record.

        Args:
            memory_id: The memory ID to update.
            status: New status ('approved', 'rejected').

        Returns:
            True if successfully updated, False if not found.
        """
        try:
            # Check if exists
            current_status = await self.async_client.hget(
                self.audit_status_key, memory_id
            )
            if not current_status:
                logger.warning("memory_not_found_in_audit_queue", memory_id=memory_id)
                return False

            # Update status
            async with self.async_client.pipeline() as pipe:
                pipe.hset(self.audit_status_key, memory_id, status)
                # Add reviewed timestamp to data
                data_json = await self.async_client.hget(self.audit_data_key, memory_id)
                if data_json:
                    try:
                        data = json.loads(data_json.decode("utf-8"))
                        data["status"] = status
                        data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                        pipe.hset(self.audit_data_key, memory_id, json.dumps(data))
                    except json.JSONDecodeError as e:
                        logger.error(
                            "failed_to_decode_json_for_memory",
                            memory_id=memory_id,
                            error=str(e),
                            exc_info=True,
                        )
                        # Continue with the update but without updating the data part
                    except UnicodeDecodeError as e:
                        logger.error(
                            "failed_to_decode_utf8_for_memory",
                            memory_id=memory_id,
                            error=str(e),
                            exc_info=True,
                        )
                        # Continue with the update but without updating the data part
                await pipe.execute()

            logger.info("updated_memory_status", memory_id=memory_id, status=status)
            return True
        except RedisError as e:
            logger.error(
                "redis_error_while_updating_audit_status",
                memory_id=memory_id,
                error=str(e),
                exc_info=True,
            )
            raise AuditError(
                f"Failed to update audit status due to Redis error: {e}"
            ) from e
        except Exception as e:
            logger.error(
                "unexpected_error_while_updating_audit_status",
                memory_id=memory_id,
                error=str(e),
                exc_info=True,
            )
            raise AuditError(
                f"Failed to update audit status due to unexpected error: {e}"
            ) from e

    async def is_memory_approved(self, memory_id: str) -> bool:
        """
        Checks if a memory has been approved by an admin.

        Args:
            memory_id: The memory ID to check.

        Returns:
            True if approved, False otherwise.
        """
        status = await self.async_client.hget(self.audit_status_key, memory_id)
        return bool(status and status.decode("utf-8") == "approved")

    async def delete_audit_record(self, memory_id: str) -> bool:
        """
        Removes an audit record from the queue.

        Args:
            memory_id: The memory ID to remove.

        Returns:
            True if successfully removed, False if not found.
        """
        # Check if exists
        exists = await self.async_client.hexists(self.audit_status_key, memory_id)
        if not exists:
            logger.warning("memory_not_found_in_audit_queue", memory_id=memory_id)
            return False

        async with self.async_client.pipeline() as pipe:
            # Remove from all Redis structures
            pipe.lrem(self.audit_queue_key, 0, memory_id)
            pipe.hdel(self.audit_status_key, memory_id)
            pipe.hdel(self.audit_data_key, memory_id)
            await pipe.execute()

        logger.info("deleted_memory_from_audit_queue", memory_id=memory_id)
        return True

    async def get_queue_length(self) -> int:
        """
        Gets the current length of the audit queue.

        Returns:
            Number of items in the queue.
        """
        return int(await self.async_client.llen(self.audit_queue_key))

    async def cleanup_processed_audits(self, days_old: int = 30) -> int:
        """
        Removes old processed (approved/rejected) audits to prevent memory bloat.

        Args:
            days_old: Remove audits older than this many days.

        Returns:
            Number of records cleaned up.
        """
        cutoff_date = datetime.now(timezone.utc).timestamp() - (days_old * 24 * 60 * 60)
        cleaned_count = 0

        # Get all memory IDs
        all_ids = await self.async_client.hkeys(self.audit_status_key)

        for memory_id_bytes in all_ids:
            memory_id = memory_id_bytes.decode("utf-8")
            status = await self.async_client.hget(self.audit_status_key, memory_id)

            if status and status.decode("utf-8") in ["approved", "rejected"]:
                # Check if old enough
                data_json = await self.async_client.hget(self.audit_data_key, memory_id)
                if data_json:
                    data = json.loads(data_json.decode("utf-8"))
                    reviewed_at_str = data.get("reviewed_at")
                    if reviewed_at_str:
                        reviewed_at = datetime.fromisoformat(
                            reviewed_at_str.replace("Z", "+00:00")
                        ).timestamp()
                        if reviewed_at < cutoff_date:
                            await self.delete_audit_record(memory_id)
                            cleaned_count += 1

        logger.info("cleaned_up_old_processed_audits", cleaned_count=cleaned_count)
        return cleaned_count

    # --- Distributed Locking for Race Condition Prevention ---

    async def acquire_lock(
        self, lock_key: str, lock_value: str, timeout: int = 30
    ) -> bool:
        """
        Acquires a distributed lock using the new DistributedAuditLock.

        Args:
            lock_key: Unique identifier for the lock
            lock_value: Unique value for this lock instance
            timeout: Lock timeout in seconds (default: 30)

        Returns:
            True if lock acquired, False if already locked
        """
        # Use the new distributed audit lock
        try:
            async with await self.distributed_lock.acquire(lock_key, timeout):
                return True
        except AuditError as e:
            logger.warning("failed_to_acquire_lock", lock_key=lock_key, error=str(e))
            return False
        except RedisError as e:
            logger.error(
                "redis_error_during_lock_acquisition", lock_key=lock_key, error=str(e)
            )
            return False

    async def release_lock(self, lock_key: str, lock_value: str) -> bool:
        """
        Releases a distributed lock using the new DistributedAuditLock.

        Args:
            lock_key: The lock key to release
            lock_value: The lock value (must match current owner)

        Returns:
            True if lock released, False if not owned or doesn't exist
        """
        # Use the new distributed audit lock for release
        try:
            await self.distributed_lock.force_release(lock_key)
            return True
        except AuditError as e:
            logger.warning("failed_to_release_lock", lock_key=lock_key, error=str(e))
            return False
        except ValueError as e:
            logger.warning(
                "value_error_during_lock_release", lock_key=lock_key, error=str(e)
            )
            return False

    async def with_lock(self, lock_key: str, timeout: int = 30) -> Any:
        """
        Context manager for distributed locking using the new DistributedAuditLock.

        Usage:
            async with audit_queue.with_lock(f"memory:{memory_id}"):
                # Critical section - memory processing
                pass
        """
        # Delegate to the new distributed audit lock
        return self.distributed_lock.acquire(lock_key, timeout)

    async def cleanup_expired_locks(
        self, _lock_prefix: str = "memory:", max_age: int = 60
    ) -> int:
        """
        Cleans up expired locks to prevent deadlocks using the new DistributedAuditLock.

        Args:
            lock_prefix: Prefix for lock keys to clean up
            max_age: Maximum age in seconds for lock cleanup

        Returns:
            Number of locks cleaned up
        """
        try:
            # Delegate to the new distributed audit lock
            return await self.distributed_lock.cleanup_expired_locks(max_age)
        except (AuditError, DatabaseError, RedisError) as e:
            # Handle errors gracefully and return 0 to indicate no locks were cleaned
            logger.warning("error_during_audit_lock_cleanup", error=str(e))
            return 0

    async def force_release_lock(self, lock_key: str) -> bool:
        """
        Forcefully releases a lock using the new DistributedAuditLock (for administrative purposes).

        Args:
            lock_key: The lock key to force release

        Returns:
            True if lock was released, False if not found
        """
        try:
            return await self.distributed_lock.force_release(lock_key)
        except AuditError as e:
            logger.error(
                "audit_error_force_releasing_lock", lock_key=lock_key, error=str(e)
            )
            return False
        except RedisError as e:
            logger.error(
                "redis_error_force_releasing_lock", lock_key=lock_key, error=str(e)
            )
            return False
        except ValueError as e:
            logger.error(
                "value_error_force_releasing_lock", lock_key=lock_key, error=str(e)
            )
            return False
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                "connection_error_force_releasing_lock", lock_key=lock_key, error=str(e)
            )
            return False

    async def get_all_audits(self) -> List[Dict[str, Any]]:
        """
        Retrieves all audit records from the queue.

        Returns:
            List of all audit records.
        """
        # Get all memory IDs
        memory_ids = await self.async_client.hkeys(self.audit_status_key)

        if not memory_ids:
            return []

        all_audits = []
        for memory_id_bytes in memory_ids:
            memory_id = memory_id_bytes.decode("utf-8")
            data_json = await self.async_client.hget(self.audit_data_key, memory_id)
            if data_json:
                data = json.loads(data_json.decode("utf-8"))
                all_audits.append(data)

        return all_audits

    async def get_audits_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Retrieves audit records filtered by status.

        Args:
            status: Status to filter by ('pending', 'approved', 'rejected')

        Returns:
            List of audit records with the specified status.
        """
        # Get all memory IDs
        memory_ids = await self.async_client.hkeys(self.audit_status_key)

        if not memory_ids:
            return []

        filtered_audits = []
        for memory_id_bytes in memory_ids:
            memory_id = memory_id_bytes.decode("utf-8")
            current_status = await self.async_client.hget(
                self.audit_status_key, memory_id
            )

            if current_status and current_status.decode("utf-8") == status:
                data_json = await self.async_client.hget(self.audit_data_key, memory_id)
                if data_json:
                    data = json.loads(data_json.decode("utf-8"))
                    filtered_audits.append(data)

        return filtered_audits

    async def get_audit_metrics(self) -> Dict[str, int]:
        """
        Returns metrics for the audit queue.

        Returns:
            Dictionary with counts of pending, approved, rejected, and total records.
        """
        # Get all memory IDs
        memory_ids = await self.async_client.hkeys(self.audit_status_key)

        if not memory_ids:
            return {"total": 0, "pending": 0, "approved": 0, "rejected": 0}

        metrics = {
            "total": len(memory_ids),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
        }

        for memory_id_bytes in memory_ids:
            memory_id = memory_id_bytes.decode("utf-8")
            status = await self.async_client.hget(self.audit_status_key, memory_id)

            if status:
                status_str = status.decode("utf-8")
                if status_str in metrics:
                    metrics[status_str] += 1

        return metrics

    async def health_check(self) -> bool:
        """
        Performs a health check on the Redis connection.

        Returns:
            True if Redis is accessible, False otherwise.
        """
        try:
            # Simple ping to check if Redis is responsive
            return bool(await self.async_client.ping())
        except RedisError as e:
            logger.error("redis_health_check_failed", error=str(e))
            return False
        except ConnectionError as e:
            logger.error("redis_health_check_failed_connection_error", error=str(e))
            return False
        except TimeoutError as e:
            logger.error("redis_health_check_failed_timeout", error=str(e))
            return False
        except Exception as e:
            logger.error("redis_health_check_failed_unexpected_error", error=str(e))
            return False

    async def get_connection_info(self) -> Dict[str, Any]:
        """
        Gets information about the Redis connection.

        Returns:
            Dictionary with connection information.
        """
        try:
            info = await self.async_client.info()
            return {
                "connected": True,
                "host": self.redis_url,
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "uptime_days": info.get("uptime_in_days", 0),
            }
        except RedisError as e:
            logger.error("redis_error_getting_connection_info", error=str(e))
            return {
                "connected": False,
                "host": self.redis_url,
                "error": f"Redis error: {str(e)}",
            }
        except ConnectionError as e:
            logger.error("connection_error_getting_redis_info", error=str(e))
            return {
                "connected": False,
                "host": self.redis_url,
                "error": f"Connection error: {str(e)}",
            }
        except TimeoutError as e:
            logger.error("timeout_getting_redis_connection_info", error=str(e))
            return {
                "connected": False,
                "host": self.redis_url,
                "error": f"Timeout: {str(e)}",
            }
        except Exception as e:
            logger.error("unexpected_error_getting_redis_connection_info", error=str(e))
            return {
                "connected": False,
                "host": self.redis_url,
                "error": f"Unexpected error: {str(e)}",
            }

    def health_check_sync(self) -> bool:
        """Synchronous wrapper for health_check"""
        import asyncio

        return asyncio.run(self.health_check())

    def get_connection_info_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_connection_info"""
        import asyncio

        return asyncio.run(self.get_connection_info())

    # Synchronous wrappers for FastAPI compatibility
    def add_audit_record_sync(self, memory: Dict[str, Any]) -> bool:
        """Synchronous wrapper for add_audit_record"""
        import asyncio

        return asyncio.run(self.add_audit_record(memory))

    def get_all_audits_sync(self) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_all_audits"""
        import asyncio

        return asyncio.run(self.get_all_audits())

    def get_audits_by_status_sync(self, status: str) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_audits_by_status"""
        import asyncio

        return asyncio.run(self.get_audits_by_status(status))

    def get_audit_metrics_sync(self) -> Dict[str, int]:
        """Synchronous wrapper for get_audit_metrics"""
        import asyncio

        return asyncio.run(self.get_audit_metrics())

    def update_audit_status_sync(self, memory_id: str, status: str) -> bool:
        """Synchronous wrapper for update_audit_status"""
        import asyncio

        return asyncio.run(self.update_audit_status(memory_id, status))

    def delete_audit_record_sync(self, memory_id: str) -> bool:
        """Synchronous wrapper for delete_audit_record"""
        import asyncio

        return asyncio.run(self.delete_audit_record(memory_id))

    def is_memory_approved_sync(self, memory_id: str) -> bool:
        """Synchronous wrapper for is_memory_approved"""
        import asyncio

        return asyncio.run(self.is_memory_approved(memory_id))


# Migration utilities for transitioning from SQLite
async def migrate_from_sqlite() -> None:
    """
    Migrates existing audit data from SQLite to Redis.
    This should be run once during deployment.
    """
    try:
        # Temporarily create an instance for migration
        migration_audit_queue = AsyncAuditQueue()

        import sqlite3

        sqlite_path = settings.BASE_DIR / "audit_queue.db"
        if not sqlite_path.exists():
            logger.info("No SQLite audit database found, skipping migration.")
            return

        # Connect to SQLite
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all records
        cursor.execute("SELECT * FROM audit_queue")
        rows = cursor.fetchall()

        migrated_count = 0
        for row in rows:
            memory = {
                "id": row["memory_id"],
                "user_query": row["user_query"],
                "agent_response": row["agent_response"],
                "ia_audit_reason": row["ia_audit_reason"],
                "ia_audit_confidence": row["ia_audit_confidence"],
            }

            success = await migration_audit_queue.add_audit_record(memory)
            if success:
                migrated_count += 1

                # Update status if not pending
                if row["status"] != "pending":
                    await migration_audit_queue.update_audit_status(
                        row["memory_id"], row["status"]
                    )

        logger.info(
            f"Migration completed: {migrated_count} records migrated from SQLite to Redis."
        )
        conn.close()

    except ImportError as e:
        logger.error(
            "import_error_during_sqlite_to_redis_migration", error=str(e), exc_info=True
        )
        raise FileProcessingError(
            f"Import error during SQLite to Redis migration: {e}"
        ) from e
    except sqlite3.Error as e:
        logger.error("sqlite_error_during_migration", error=str(e), exc_info=True)
        raise DatabaseError(f"SQLite error during migration: {e}") from e
    except RedisError as e:
        logger.error("redis_error_during_migration", error=str(e), exc_info=True)
        raise DatabaseError(f"Redis error during migration: {e}") from e
    except json.JSONDecodeError as e:
        logger.error("json_decode_error_during_migration", error=str(e), exc_info=True)
        raise DataParsingError(f"JSON decode error during migration: {e}") from e
    except FileNotFoundError as e:
        logger.error("file_not_found_during_migration", error=str(e), exc_info=True)
        raise FileProcessingError(f"File not found during migration: {e}") from e
    except (ValueError, TypeError) as e:
        logger.critical(
            "unexpected_error_during_sqlite_to_redis_migration",
            error=str(e),
            exc_info=True,
        )
        raise AuditError(
            f"Unexpected error during SQLite to Redis migration: {e}"
        ) from e
