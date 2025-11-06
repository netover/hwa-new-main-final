import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from resync.core.connection_pool_manager import get_connection_pool_manager
from resync.settings import settings
import redis.asyncio as redis

logger = logging.getLogger(__name__)

DATABASE_PATH = settings.BASE_DIR / "audit_queue.db"

# Redis Streams configuration
AUDIT_STREAM_KEY = "audit_queue:stream"
AUDIT_CONSUMER_GROUP = "audit_processors"
AUDIT_CONSUMER_NAME = "processor_1"


async def get_redis_client() -> redis.Redis:
    """Gets a Redis client for audit operations."""
    return redis.Redis.from_url(settings.REDIS_URL)


async def ensure_consumer_group():
    """Ensures the consumer group exists for audit processing."""
    try:
        client = await get_redis_client()
        await client.xgroup_create(
            AUDIT_STREAM_KEY, AUDIT_CONSUMER_GROUP, "$", mkstream=True
        )
        logger.info("consumer_group_created", group=AUDIT_CONSUMER_GROUP)
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.debug("consumer_group_already_exists", group=AUDIT_CONSUMER_GROUP)
        else:
            logger.error("failed_to_create_consumer_group", error=str(e))
    except Exception as e:
        logger.error("unexpected_error_creating_consumer_group", error=str(e))


async def add_audit_record_async(memory: Dict[str, Any]) -> Optional[str]:
    """
    Adds a new memory to the audit queue using Redis Streams.
    Returns the message ID or None if failed.
    """
    try:
        # Validate input
        validated_memory = _validate_audit_record(memory)

        client = await get_redis_client()

        # Prepare data for Redis Stream
        stream_data = {
            "memory_id": validated_memory["id"],
            "user_query": validated_memory["user_query"],
            "agent_response": validated_memory["agent_response"],
            "status": "pending",
            "created_at": validated_memory.get("created_at", "*"),
        }

        if validated_memory.get("ia_audit_reason"):
            stream_data["ia_audit_reason"] = validated_memory["ia_audit_reason"]
        if validated_memory.get("ia_audit_confidence") is not None:
            stream_data["ia_audit_confidence"] = str(
                validated_memory["ia_audit_confidence"]
            )

        # Add to Redis Stream
        message_id = await client.xadd(AUDIT_STREAM_KEY, stream_data)

        logger.debug(
            "added_memory_to_redis_stream",
            memory_id=validated_memory["id"],
            message_id=message_id,
        )
        return message_id

    except Exception as e:
        logger.error(
            "failed_to_add_audit_record_to_redis",
            error=str(e),
            memory_id=memory.get("id"),
        )
        # Fallback to SQLite
        return add_audit_record(memory)


async def get_pending_audits_async() -> List[Dict[str, Any]]:
    """
    Retrieves pending audit records from Redis Streams.
    Falls back to SQLite if Redis is unavailable.
    """
    try:
        client = await get_redis_client()

        # Read pending messages from stream
        messages = await client.xreadgroup(
            AUDIT_CONSUMER_GROUP,
            AUDIT_CONSUMER_NAME,
            {AUDIT_STREAM_KEY: ">"},
            count=100,
        )

        audits = []
        for stream_name, message_list in messages:
            for message_id, message_data in message_list:
                if message_data.get("status") == "pending":
                    audit_record = {
                        "id": message_id,
                        "memory_id": message_data.get("memory_id"),
                        "user_query": message_data.get("user_query"),
                        "agent_response": message_data.get("agent_response"),
                        "ia_audit_reason": message_data.get("ia_audit_reason"),
                        "ia_audit_confidence": float(
                            message_data.get("ia_audit_confidence", 0)
                        ),
                        "status": message_data.get("status"),
                        "created_at": message_data.get("created_at"),
                    }
                    audits.append(audit_record)

        logger.debug("retrieved_pending_audits_from_redis", count=len(audits))
        return audits

    except Exception as e:
        logger.error("failed_to_get_pending_audits_from_redis", error=str(e))
        # Fallback to SQLite
        return get_pending_audits()


async def update_audit_status_async(memory_id: str, status: str) -> bool:
    """
    Updates audit status in Redis Streams.
    Falls back to SQLite if Redis is unavailable.
    """
    try:
        client = await get_redis_client()

        # Find and update the message
        messages = await client.xread({AUDIT_STREAM_KEY: "0"}, count=1000)

        for stream_name, message_list in messages:
            for message_id, message_data in message_list:
                if message_data.get("memory_id") == memory_id:
                    # Update the message (Redis Streams are immutable, so we add a new message)
                    updated_data = message_data.copy()
                    updated_data["status"] = status
                    updated_data["reviewed_at"] = "*"

                    await client.xadd(AUDIT_STREAM_KEY, updated_data)
                    logger.info(
                        "updated_audit_status_in_redis",
                        memory_id=memory_id,
                        status=status,
                    )
                    return True

        logger.warning("audit_record_not_found_in_redis", memory_id=memory_id)
        return False

    except Exception as e:
        logger.error("failed_to_update_audit_status_in_redis", error=str(e))
        # Fallback to SQLite
        return update_audit_status(memory_id, status)


def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a TWS-optimized SQLite database connection."""
    conn = sqlite3.connect(DATABASE_PATH)

    # TWS-specific SQLite optimizations
    conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
    conn.execute("PRAGMA synchronous = NORMAL")  # Better performance
    conn.execute("PRAGMA cache_size = 10000")  # 10MB cache
    conn.execute("PRAGMA temp_store = memory")  # Memory temp tables
    conn.execute("PRAGMA foreign_keys = ON")  # Data integrity

    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


@asynccontextmanager
async def get_db_connection_pool():
    """
    Get a database connection from the connection pool.
    Falls back to direct connection if pool is not available.

    Yields:
        Database connection (SQLAlchemy Engine)
    """
    try:
        pool_manager = await get_connection_pool_manager()
        db_pool = pool_manager.get_pool("database")

        if db_pool:
            # Use connection from pool
            async with db_pool.get_connection() as engine:
                yield engine
        else:
            # Fallback to direct SQLite connection
            logger.warning(
                "Database connection pool not available, using direct connection"
            )
            yield get_db_connection()

    except Exception as e:
        logger.error("failed_to_get_database_connection_from_pool", error=str(e))
        # Fallback to direct connection on any error
        yield get_db_connection()


def initialize_database() -> None:
    """Initializes the database, creating the audit_queue table if it doesn't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL UNIQUE,
                user_query TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                ia_audit_reason TEXT,
                ia_audit_confidence REAL,
                status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            );
        """
        )
        conn.commit()
    logger.info("database_initialized", database_path=DATABASE_PATH)


def _validate_audit_record(memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive input validation for audit records based on fuzzing failures.
    """
    if not isinstance(memory, dict):
        raise TypeError("Memory must be a dictionary")

    if memory is None:
        raise ValueError("Memory cannot be None")

    validated = {}

    # ID VALIDATION - CRITICAL FIELD
    memory_id = memory.get("id")
    if memory_id is None:
        raise ValueError("Memory ID is required")
    elif not isinstance(memory_id, (str, int)):
        raise TypeError("Memory ID must be string or int")
    else:
        str_id = str(memory_id)
        if len(str_id) == 0:
            raise ValueError("Memory ID cannot be empty")
        if len(str_id) > 255:
            raise ValueError("Memory ID too long (max 255)")
        if "\x00" in str_id:
            raise ValueError("Memory ID cannot contain null bytes")
        validated["id"] = str_id

    # USER QUERY VALIDATION
    user_query = memory.get("user_query")
    if user_query is not None:
        if not isinstance(user_query, str):
            raise TypeError("User query must be string")
        if len(user_query) > 10000:
            raise ValueError("User query too long (max 10000)")
        if "\x00" in user_query:
            raise ValueError("User query cannot contain null bytes")
        validated["user_query"] = user_query
    else:
        raise ValueError("User query is required")

    # AGENT RESPONSE VALIDATION
    agent_response = memory.get("agent_response")
    if agent_response is not None:
        if not isinstance(agent_response, str):
            raise TypeError("Agent response must be string")
        if len(agent_response) > 50000:
            raise ValueError("Agent response too long (max 50000)")
        if "\x00" in agent_response:
            raise ValueError("Agent response cannot contain null bytes")
        validated["agent_response"] = agent_response
    else:
        raise ValueError("Agent response is required")

    # OPTIONAL FIELDS WITH VALIDATION
    ia_audit_reason = memory.get("ia_audit_reason")
    if ia_audit_reason is not None:
        if not isinstance(ia_audit_reason, str):
            raise TypeError("IA audit reason must be string")
        if len(ia_audit_reason) > 1000:
            raise ValueError("IA audit reason too long (max 1000)")
        validated["ia_audit_reason"] = ia_audit_reason

    ia_audit_confidence = memory.get("ia_audit_confidence")
    if ia_audit_confidence is not None:
        try:
            confidence_float = float(ia_audit_confidence)
            if not (0.0 <= confidence_float <= 1.0):
                raise ValueError("IA audit confidence must be between 0.0 and 1.0")
            validated["ia_audit_confidence"] = confidence_float
        except (ValueError, TypeError):
            raise ValueError("IA audit confidence must be a number between 0.0 and 1.0")

    return validated


def add_audit_record(memory: Dict[str, Any]) -> Optional[int]:
    """
    Adds a new memory to the audit queue for review with input validation.
    Returns the ID of the new record or None if already exists.
    """
    # FUZZING-HARDENED INPUT VALIDATION
    validated_memory = _validate_audit_record(memory)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO audit_queue (
                    memory_id, user_query, agent_response,
                    ia_audit_reason, ia_audit_confidence, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    validated_memory["id"],
                    validated_memory["user_query"],
                    validated_memory["agent_response"],
                    validated_memory.get("ia_audit_reason"),
                    validated_memory.get("ia_audit_confidence"),
                    "pending",
                ),
            )
            conn.commit()
            logger.debug("Added memory %s to audit queue.", validated_memory["id"])
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.debug(
                "Memory %s already exists in audit queue. Skipping.",
                validated_memory["id"],
            )
            return None
        except Exception as e:
            logger.error(
                "Error adding memory %s to audit queue: %s",
                memory.get("id"),
                e,
                exc_info=True,
            )
            return None


def add_audit_records_batch(memories: List[Dict[str, Any]]) -> List[Optional[int]]:
    """
    Batch insert multiple audit records for better performance.

    Args:
        memories: List of memory dictionaries

    Returns:
        List of record IDs (None for duplicates)
    """
    if not memories:
        return []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        record_ids = []

        for memory in memories:
            try:
                cursor.execute(
                    """
                    INSERT INTO audit_queue (
                        memory_id, user_query, agent_response,
                        ia_audit_reason, ia_audit_confidence, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        memory["id"],
                        memory["user_query"],
                        memory["agent_response"],
                        memory.get("ia_audit_reason"),
                        memory.get("ia_audit_confidence"),
                        "pending",
                    ),
                )
                record_ids.append(cursor.lastrowid)
            except sqlite3.IntegrityError:
                logger.debug(
                    "Memory %s already exists in audit queue. Skipping.", memory["id"]
                )
                record_ids.append(None)
            except Exception as e:
                logger.error(
                    "Error adding memory %s to audit queue: %s",
                    memory.get("id"),
                    e,
                    exc_info=True,
                )
                record_ids.append(None)

        conn.commit()
        logger.info(
            "Batch inserted %d audit records",
            len([id for id in record_ids if id is not None]),
        )
        return record_ids


def get_pending_audits() -> List[Dict[str, Any]]:
    """
    Retrieves all memories currently pending review.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_queue WHERE status = 'pending' ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_audit_status(memory_id: str, status: str) -> bool:
    """
    Updates the status of an audit record.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE audit_queue
            SET status = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE memory_id = ?
        """,
            (status, memory_id),
        )
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("Updated memory %s status to %s.", memory_id, status)
            return True
        logger.warning("Memory %s not found for status update.", memory_id)


def delete_audit_record(memory_id: str) -> bool:
    """
    Deletes an audit record from the queue.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM audit_queue WHERE memory_id = ?", (memory_id,))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("Deleted memory %s from audit queue.", memory_id)
            return True
        logger.warning("Memory %s not found for deletion from audit queue.", memory_id)


def is_memory_approved(memory_id: str) -> bool:
    """
    Checks if a memory has been approved by an admin.
    Now supports Redis Streams as primary source with SQLite fallback.

    Args:
        memory_id: The ID of the memory to check.

    Returns:
        True if the memory is approved, False otherwise.
    """
    if USE_REDIS_STREAMS:
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def check_approval():
                client = await get_redis_client()
                messages = await client.xread({AUDIT_STREAM_KEY: "0"}, count=1000)
                for stream_name, message_list in messages:
                    for message_id, message_data in message_list:
                        if message_data.get("memory_id") == memory_id:
                            return message_data.get("status") == "approved"
                return False

            result = loop.run_until_complete(check_approval())
            loop.close()
            return result

        except Exception as e:
            logger.error("failed_to_check_approval_in_redis", error=str(e))

    # SQLite fallback
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM audit_queue WHERE memory_id = ?", (memory_id,)
        )
        row = cursor.fetchone()
        return row is not None and row["status"] == "approved"


async def initialize_redis_streams():
    """Initialize Redis Streams for audit processing."""
    try:
        await ensure_consumer_group()
        logger.info("redis_streams_initialized_for_audit")
    except Exception as e:
        logger.error("failed_to_initialize_redis_streams", error=str(e))


def add_audit_record_redis(memory: Dict[str, Any]) -> Optional[str]:
    """
    Synchronous wrapper for Redis Streams audit record addition.
    Falls back to SQLite if async operation fails.
    """
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(add_audit_record_async(memory))
        loop.close()
        return result
    except Exception as e:
        logger.error("failed_to_add_audit_record_via_redis_wrapper", error=str(e))
        return add_audit_record(memory)


def get_pending_audits_redis() -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for Redis Streams pending audits retrieval.
    Falls back to SQLite if async operation fails.
    """
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_pending_audits_async())
        loop.close()
        return result
    except Exception as e:
        logger.error("failed_to_get_pending_audits_via_redis_wrapper", error=str(e))
        return get_pending_audits()


def update_audit_status_redis(memory_id: str, status: str) -> bool:
    """
    Synchronous wrapper for Redis Streams status updates.
    Falls back to SQLite if async operation fails.
    """
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(update_audit_status_async(memory_id, status))
        loop.close()
        return result
    except Exception as e:
        logger.error("failed_to_update_audit_status_via_redis_wrapper", error=str(e))
        return update_audit_status(memory_id, status)


# Configuration flag to enable Redis Streams
USE_REDIS_STREAMS = os.environ.get("USE_REDIS_AUDIT_STREAMS", "false").lower() == "true"


def add_audit_record(memory: Dict[str, Any]) -> Optional[int]:
    """
    Adds a new memory to the audit queue for review with input validation.
    Returns the ID of the new record or None if already exists.
    Now supports Redis Streams as primary storage with SQLite fallback.
    """
    if USE_REDIS_STREAMS:
        # Try Redis Streams first
        redis_result = add_audit_record_redis(memory)
        if redis_result:
            return int(redis_result.split("-")[0]) if "-" in redis_result else 1
        # Fallback to SQLite if Redis fails
        logger.warning("falling_back_to_sqlite_after_redis_failure")

    # SQLite implementation (existing code)
    validated_memory = _validate_audit_record(memory)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO audit_queue (
                    memory_id, user_query, agent_response,
                    ia_audit_reason, ia_audit_confidence, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    validated_memory["id"],
                    validated_memory["user_query"],
                    validated_memory["agent_response"],
                    validated_memory.get("ia_audit_reason"),
                    validated_memory.get("ia_audit_confidence"),
                    "pending",
                ),
            )
            conn.commit()
            logger.debug("Added memory %s to audit queue.", validated_memory["id"])
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.debug(
                "Memory %s already exists in audit queue. Skipping.",
                validated_memory["id"],
            )
            return None
        except Exception as e:
            logger.error(
                "Error adding memory %s to audit queue: %s",
                memory.get("id"),
                e,
                exc_info=True,
            )
            return None


def get_pending_audits() -> List[Dict[str, Any]]:
    """
    Retrieves all memories currently pending review.
    Now supports Redis Streams as primary source with SQLite fallback.
    """
    if USE_REDIS_STREAMS:
        # Try Redis Streams first
        redis_audits = get_pending_audits_redis()
        if redis_audits:
            return redis_audits
        # Fallback to SQLite if Redis fails
        logger.warning("falling_back_to_sqlite_after_redis_failure")

    # SQLite implementation (existing code)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_queue WHERE status = 'pending' ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_audit_status(memory_id: str, status: str) -> bool:
    """
    Updates the status of an audit record.
    Now supports Redis Streams as primary storage with SQLite fallback.
    """
    if USE_REDIS_STREAMS:
        # Try Redis Streams first
        if update_audit_status_redis(memory_id, status):
            return True
        # Fallback to SQLite if Redis fails
        logger.warning("falling_back_to_sqlite_after_redis_failure")

    # SQLite implementation (existing code)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE audit_queue
            SET status = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE memory_id = ?
        """,
            (status, memory_id),
        )
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("Updated memory %s status to %s.", memory_id, status)
            return True
        logger.warning("Memory %s not found for status update.", memory_id)


# Initialize both systems
initialize_database()

if USE_REDIS_STREAMS:
    import asyncio

    asyncio.run(initialize_redis_streams())
