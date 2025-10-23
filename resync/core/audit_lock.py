"""
Distributed Audit Lock for Resync

This module provides a dedicated distributed locking mechanism for audit operations
to prevent race conditions during concurrent memory processing.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, cast

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from resync.core.exceptions import AuditError, DatabaseError
from resync.settings import settings

logger = logging.getLogger(__name__)


class DistributedAuditLock:
    """
    A distributed lock implementation using Redis for audit operations.

    This class provides atomic locking to prevent race conditions when multiple
    IA Auditor processes attempt to process the same memory simultaneously.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Initialize the distributed audit lock.

        Args:
            redis_url: Redis connection URL. Defaults to environment variable or localhost.
        """
        self.redis_url: str = str(
            redis_url
            or getattr(settings, "REDIS_URL", "redis://localhost:6379/1")
            or "redis://localhost:6379/1"
        )
        self.client: Optional[AsyncRedis] = None
        self._lock_prefix: str = "audit_lock"
        self.release_script_sha: Optional[str] = None

        logger.info(
            "DistributedAuditLock initialized with Redis", redis_url=self.redis_url
        )

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self.client is None:
            self.client = AsyncRedis.from_url(self.redis_url)
            # Load Lua script on connection
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            self.release_script_sha = await self.client.script_load(lua_script)
            # Test connection
            await self.client.ping()
            logger.info("DistributedAuditLock connected to Redis")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("DistributedAuditLock disconnected from Redis")

    def _get_lock_key(self, memory_id: str) -> str:
        if not isinstance(memory_id, str) or len(memory_id) == 0:
            raise ValueError("Invalid memory_id - must be a non-empty string")
        """
        Generate a unique lock key for a memory ID.

        Args:
            memory_id: The memory ID to generate a lock key for.

        Returns:
            A unique lock key string.
        """
        return f"{self._lock_prefix}:{memory_id}"

    async def acquire(self, memory_id: str, timeout: int = 5) -> "AuditLockContext":
        """
        Acquire a distributed lock for a memory ID.

        Args:
            memory_id: The memory ID to lock.
            timeout: Lock timeout in seconds.

        Returns:
            An AuditLockContext instance.
        """
        if self.client is None:
            await self.connect()

        self.client = cast(AsyncRedis, self.client)

        lock_key = self._get_lock_key(memory_id)
        return AuditLockContext(self.client, lock_key, timeout, self.release_script_sha)

    async def is_locked(self, memory_id: str) -> bool:
        """
        Check if a memory ID is currently locked.

        Args:
            memory_id: The memory ID to check.

        Returns:
            True if locked, False otherwise.
        """
        if self.client is None:
            await self.connect()

        self.client = cast(AsyncRedis, self.client)

        lock_key = self._get_lock_key(memory_id)
        return int(await self.client.exists(lock_key)) == 1

    async def force_release(self, memory_id: str) -> bool:
        """
        Forcefully release a lock for a memory ID (for administrative purposes).

        Args:
            memory_id: The memory ID to unlock.

        Returns:
            True if lock was released, False if not found.
        """
        if self.client is None:
            await self.connect()

        self.client = cast(AsyncRedis, self.client)

        lock_key = self._get_lock_key(memory_id)
        result = await self.client.delete(lock_key)
        if result:
            logger.warning(
                "forcefully_released_audit_lock_for_memory", memory_id=memory_id
            )
        return bool(result)

    async def cleanup_expired_locks(self, max_age: int = 60) -> int:
        """
        Clean up expired locks to prevent deadlocks.

        Args:
            max_age: Maximum age in seconds for lock cleanup.

        Returns:
            Number of locks cleaned up.
        """
        if self.client is None:
            await self.connect()

        self.client = cast(AsyncRedis, self.client)

        try:
            cleaned_count: int = 0

            # Get all audit lock keys
            lock_pattern = f"{self._lock_prefix}:*"
            lock_keys = await self.client.keys(lock_pattern)

            for lock_key_bytes in lock_keys:
                lock_key = lock_key_bytes.decode("utf-8")

                # Check if lock is old enough to be considered expired
                ttl = await self.client.ttl(lock_key)
                if ttl is None or ttl <= max_age:
                    # Remove locks that are too old
                    await self.client.delete(lock_key)
                    cleaned_count += 1

            if cleaned_count > 0:
                logger.info("Cleaned up %d expired audit locks", cleaned_count)

            return cleaned_count

        except RedisError as e:
            logger.error("Redis error cleaning up expired audit locks: %s", e)
            raise DatabaseError(f"Redis error during audit lock cleanup: {e}") from e
        except UnicodeDecodeError as e:
            logger.error("Unicode decode error in audit lock cleanup: %s", e)
            raise AuditError(f"Unicode decode error in audit lock cleanup: {e}") from e
        except ValueError as e:
            logger.error("Value error in audit lock cleanup: %s", e)
            raise AuditError(f"Value error in audit lock cleanup: {e}") from e
        except Exception as e:
            logger.critical(
                "Unexpected critical error cleaning up expired audit locks.",
                exc_info=True,
            )
            raise AuditError(
                "Unexpected critical error during audit lock cleanup"
            ) from e


class AuditLockContext:
    """
    Context manager for distributed audit locks.

    Usage:
        async with audit_lock.acquire(memory_id, timeout=5):
            # Critical section - memory processing
            pass
    """

    def __init__(
        self,
        client: AsyncRedis,
        lock_key: str,
        timeout: int,
        release_script_sha: Optional[str] = None,
    ) -> None:
        """
        Initialize the lock context.

        Args:
            client: Redis async client.
            lock_key: The lock key to acquire.
            timeout: Lock timeout in seconds.
        """
        self.client: AsyncRedis = client
        self.lock_key: str = lock_key
        self.timeout: int = timeout
        self.lock_value: Optional[str] = None
        self._locked: bool = False
        self.release_script_sha: Optional[str] = release_script_sha

    async def __aenter__(self) -> "AuditLockContext":
        """Acquire the lock."""
        self.lock_value = str(uuid.uuid4())

        # Use Redis SET with NX and PX for atomic lock acquisition
        success = await self.client.set(
            self.lock_key,
            self.lock_value,
            nx=True,  # Only set if key doesn't exist
            px=self.timeout * 1000,  # Convert seconds to milliseconds
        )

        if success:
            self._locked = True
            logger.debug("Acquired audit lock: %s", self.lock_key)
            return self
        else:
            raise AuditError(f"Could not acquire audit lock: {self.lock_key}")

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Release the lock."""
        if self._locked and self.lock_value:
            await self._release_lock()

    async def _release_lock(self) -> None:
        """Release the lock if owned by this instance."""
        if not self.lock_value:
            return

        # Validate lock key and value
        if not isinstance(self.lock_key, str) or len(self.lock_key) == 0:
            raise ValueError("Invalid lock key format - must be non-empty string")

        if (
            not isinstance(self.lock_value, str)
            or len(self.lock_value) != 36
            or not self.lock_value.count("-") == 4
        ):
            raise ValueError("Invalid lock value (must be a UUID)")

        try:
            # Use EVALSHA for atomic check-and-delete
            if self.release_script_sha:
                result = await self.client.evalsha(
                    self.release_script_sha, 1, self.lock_key, self.lock_value
                )  [misc]
            else:
                # Fallback to eval if script not loaded
                logger.warning("Using eval fallback - script not loaded")
                lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                result = await self.client.eval(
                    lua_script, 1, self.lock_key, self.lock_value
                )  [misc]

            if result == 1:
                logger.debug("successfully_released_audit_lock", lock_key=self.lock_key)
            else:
                # Check current lock value to determine if it was already expired or not owned
                current_value = await self.client.get(self.lock_key)
                if current_value is not None:
                    logger.warning(
                        f"Failed to release audit lock: {self.lock_key} (not owned by this instance)"
                    )
                else:
                    logger.debug(
                        f"Audit lock {self.lock_key} was already expired/removed"
                    )

        except RedisError as e:
            logger.error("Redis error during lock release: %s", e)
            raise DatabaseError(f"Redis error during lock release: {e}") from e
        except ValueError as e:
            logger.error("Value error during lock release: %s", e)
            raise AuditError(f"Value error during lock release: {e}") from e
        except Exception as e:
            logger.error("Unexpected error during lock release", error=str(e))
            logger.error(
                "lock_details",
                key=self.lock_key,
                value=self.lock_value[:8] if self.lock_value else None,
            )
            raise AuditError(f"Unexpected error during lock release: {e}") from e

    async def release(self) -> None:
        """Manually release the lock."""
        await self._release_lock()


@asynccontextmanager
async def distributed_audit_lock(
    memory_id: str, timeout: int = 5
) -> AsyncIterator[None]:
    """
    Convenience context manager for distributed audit locking.

    Args:
        memory_id: The memory ID to lock.
        timeout: Lock timeout in seconds.

    Usage:
        async with distributed_audit_lock(memory_id, timeout=5):
            # Critical section - memory processing
            pass
    """
    lock = DistributedAuditLock()
    async with await lock.acquire(memory_id, timeout):
        yield


# For backward compatibility, provide a shared instance if needed
# This should be initialized during application startup and injected
# as a dependency rather than using global state
def get_audit_lock() -> DistributedAuditLock:
    """
    Factory function to get an audit lock instance.
    This helps with dependency injection and testing.
    """
    return DistributedAuditLock()
