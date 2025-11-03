"""
Connection pool manager implementation for the Resync project.
Separated to follow Single Responsibility Principle.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from resync.settings import settings

from resync.core.exceptions import TWSConnectionError
from resync.core.pools.base_pool import (
    ConnectionPool,
    ConnectionPoolConfig,
    ConnectionPoolStats,
)
from resync.core.pools.db_pool import DatabaseConnectionPool
from resync.core.pools.http_pool import HTTPConnectionPool
from resync.core.pools.redis_pool import RedisConnectionPool

# --- Logging Setup ---
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


# Global lock and instance for thread-safe singleton
_manager_lock = asyncio.Lock()
_manager_instance: ConnectionPoolManager | None = None


async def get_connection_pool_manager() -> ConnectionPoolManager:
    """
    Factory function to get the connection pool manager instance.
    This ensures the manager is properly initialized before use.
    """
    global _manager_instance

    # Fast path: if already initialized, return immediately
    if _manager_instance is not None and _manager_instance._initialized:
        return _manager_instance

    # Slow path: need to initialize
    async with _manager_lock:
        # Double-check after acquiring lock
        if _manager_instance is not None and _manager_instance._initialized:
            return _manager_instance

        # Create and initialize new instance
        if _manager_instance is None:
            _manager_instance = ConnectionPoolManager()

        if not _manager_instance._initialized:
            await _manager_instance.initialize()

        return _manager_instance


async def reset_connection_pool_manager() -> None:
    """
    Reset the singleton instance (useful for testing).

    Warning: This should only be called in test environments.
    """
    global _manager_instance

    async with _manager_lock:
        if _manager_instance is not None:
            try:
                await _manager_instance.close_all()
            except Exception as e:
                logger.error(f"Error closing manager during reset: {e}")
            finally:
                _manager_instance = None


class ConnectionPoolManager:
    """Central manager for all connection pools."""

    def __init__(self) -> None:
        self.pools: dict[str, ConnectionPool] = {}
        self._initialized = False
        self._shutdown = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize all connection pools."""
        if self._initialized or self._shutdown:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                # Initialize database connection pool
                # Handle missing settings gracefully for testing
                try:
                    db_pool_min_size = settings.DB_POOL_MIN_SIZE
                except AttributeError:
                    db_pool_min_size = 0

                if db_pool_min_size > 0:
                    try:
                        db_url = getattr(
                            settings,
                            "DATABASE_URL",
                            "sqlite+aiosqlite:///:memory:",
                        )
                    except AttributeError:
                        db_url = "sqlite+aiosqlite:///:memory:"

                    db_config = ConnectionPoolConfig(
                        pool_name="database",
                        min_size=db_pool_min_size,
                        max_size=settings.DB_POOL_MAX_SIZE,
                        idle_timeout=settings.DB_POOL_IDLE_TIMEOUT,
                        connection_timeout=settings.DB_POOL_CONNECT_TIMEOUT,
                        health_check_interval=settings.DB_POOL_HEALTH_CHECK_INTERVAL,
                        max_lifetime=settings.DB_POOL_MAX_LIFETIME,
                    )
                    db_pool = DatabaseConnectionPool(db_config, db_url)
                    await db_pool.initialize()
                    self.pools["database"] = db_pool

                # Initialize Redis connection pool
                try:
                    redis_pool_min_size = settings.REDIS_POOL_MIN_SIZE
                except AttributeError:
                    redis_pool_min_size = 0

                if redis_pool_min_size > 0:
                    try:
                        redis_url = settings.REDIS_URL
                    except AttributeError:
                        redis_url = "redis://localhost:6379"

                    redis_config = ConnectionPoolConfig(
                        pool_name="redis",
                        min_size=redis_pool_min_size,
                        max_size=settings.REDIS_POOL_MAX_SIZE,
                        idle_timeout=settings.REDIS_POOL_IDLE_TIMEOUT,
                        connection_timeout=settings.REDIS_POOL_CONNECT_TIMEOUT,
                        health_check_interval=settings.REDIS_POOL_HEALTH_CHECK_INTERVAL,
                        max_lifetime=settings.REDIS_POOL_MAX_LIFETIME,
                    )
                    redis_pool = RedisConnectionPool(redis_config, redis_url)
                    await redis_pool.initialize()
                    self.pools["redis"] = redis_pool

                # Initialize HTTP connection pool for TWS
                try:
                    http_pool_min_size = settings.HTTP_POOL_MIN_SIZE
                except AttributeError:
                    http_pool_min_size = 0

                if http_pool_min_size > 0:
                    try:
                        tws_base_url = getattr(
                            settings, "TWS_BASE_URL", "http://localhost:8000"
                        )
                    except AttributeError:
                        tws_base_url = "http://localhost:8000"

                    http_config = ConnectionPoolConfig(
                        pool_name="tws_http",
                        min_size=http_pool_min_size,
                        max_size=settings.HTTP_POOL_MAX_SIZE,
                        idle_timeout=settings.HTTP_POOL_IDLE_TIMEOUT,
                        connection_timeout=settings.HTTP_POOL_CONNECT_TIMEOUT,
                        health_check_interval=settings.HTTP_POOL_HEALTH_CHECK_INTERVAL,
                        max_lifetime=settings.HTTP_POOL_MAX_LIFETIME,
                    )
                    http_pool = HTTPConnectionPool(http_config, tws_base_url)
                    await http_pool.initialize()
                    self.pools["tws_http"] = http_pool

                self._initialized = True
                logger.info(
                    "Connection pool manager initialized with %d pools",
                    len(self.pools),
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize connection pool manager: %s", e
                )
                raise TWSConnectionError(
                    f"Failed to initialize connection pool manager: {e}"
                ) from e

    async def get_pool(self, pool_name: str) -> ConnectionPool | None:
        """Get a specific connection pool by name."""
        return self.pools.get(pool_name)

    def get_pool_stats(self) -> dict[str, ConnectionPoolStats]:
        """Get statistics for all pools."""
        stats = {}
        for name, pool in self.pools.items():
            stats[name] = pool.stats
        return stats

    async def health_check_all(self) -> dict[str, bool]:
        """Perform health checks on all pools."""
        results = {}
        for name, pool in self.pools.items():
            try:
                results[name] = await pool.health_check()
            except Exception as e:
                logger.error(f"Health check failed for pool {name}: {e}")
                results[name] = False
        return results

    async def close_all(self) -> None:
        """Close all connection pools."""
        if not self._initialized or self._shutdown:
            return

        async with self._lock:
            if self._shutdown:
                return

            for name, pool in self.pools.items():
                try:
                    await pool.close()
                except Exception as e:
                    logger.error(f"Error closing {name} pool: {e}")

            self._shutdown = True
            logger.info("All connection pools closed")

    def is_pool_healthy(self, pool_name: str) -> bool:
        """
        Synchronously determine whether a given pool is healthy.

        This helper wraps the asynchronous ``health_check`` coroutine for a
        specific pool into a synchronous call.  It should only be used in
        contexts where an event loop is not already running (e.g., property
        checks) to avoid runtime errors.  If the specified pool does not
        exist or health check fails, it returns ``False``.

        Args:
            pool_name: The name of the connection pool to check.

        Returns:
            ``True`` if the pool exists and reports a healthy status, else
            ``False``.
        """
        pool = self.pools.get(pool_name)
        if not pool:
            return False
        try:
            # If no event loop is running, create one to run the async check.
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # In an existing event loop context; schedule the check and
                # wait for the result synchronously.  Use ``asyncio.run``
                # only when no loop is running.
                future = asyncio.ensure_future(pool.health_check())
                # Wait up to 2 seconds for health check to complete
                return loop.run_until_complete(asyncio.wait_for(future, 2.0))
            else:
                return asyncio.run(pool.health_check())
        except Exception:
            return False




