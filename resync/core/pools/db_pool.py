"""
Database connection pool implementation for the Resync project.
Separated to follow Single Responsibility Principle.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import QueuePool

from resync.core.exceptions import DatabaseError
from resync.core.pools.base_pool import ConnectionPool, ConnectionPoolConfig

# --- Logging Setup ---
logger = logging.getLogger(__name__)


class DatabaseConnectionPool(ConnectionPool[AsyncEngine]):
    """Database connection pool with advanced features."""

    def __init__(self, config: ConnectionPoolConfig, database_url: str):
        super().__init__(config)
        self.database_url = database_url
        self._async_engine: Optional[AsyncEngine] = None
        self._async_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None

    async def _setup_pool(self) -> None:
        """Setup database connection pool with optimized settings."""
        try:
            # Configure async SQLAlchemy engine with connection pooling
            # Use the database URL from settings with appropriate pooling
            self._async_engine = create_async_engine(
                self.database_url,
                poolclass=QueuePool,  # Use queue-based pooling for async
                pool_size=self.config.min_size,
                max_overflow=self.config.max_size - self.config.min_size,
                pool_pre_ping=True,  # Verify connections are alive before use
                pool_recycle=self.config.max_lifetime,  # Recycle connections after max lifetime
                echo=False,  # Turn off SQL echo in production
                pool_timeout=self.config.connection_timeout,
            )

            # Create async sessionmaker for creating sessions
            self._async_sessionmaker = async_sessionmaker(
                self._async_engine,
                expire_on_commit=False,
                class_=None,
                sync_session_class=None,
            )

            logger.info(
                f"Database connection pool '{self.config.pool_name}' initialized with {self.config.min_size}-{self.config.max_size} connections"
            )
        except Exception as e:
            logger.error(f"Failed to setup database connection pool: {e}")
            raise DatabaseError(f"Failed to setup database connection pool: {e}") from e

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[AsyncSession]:
        """Get a database connection from the pool."""
        if not self._initialized or self._shutdown:
            raise DatabaseError("Database pool not initialized or shutdown")

        start_time = time.time()
        success = False

        try:
            # Record pool request
            await self.increment_stat("pool_hits")

            # Add timeout enforcement
            try:
                async with asyncio.timeout(self.config.connection_timeout):
                    # Get async session from sessionmaker
                    async with self._async_sessionmaker() as session:
                        # Increment active connections and creations only when session is acquired
                        await self.increment_stat("active_connections")
                        await self.increment_stat("connection_creations")

                        try:
                            yield session
                            await session.commit()
                            success = True
                        except SQLAlchemyError as e:
                            await session.rollback()
                            await self.increment_stat("connection_errors")
                            logger.warning(f"Database error in session: {e}")
                            raise DatabaseError(
                                f"Database operation failed: {e}"
                            ) from e
                        except Exception as e:
                            await session.rollback()
                            await self.increment_stat("connection_errors")
                            logger.error(
                                f"Unexpected error in session: {e}", exc_info=True
                            )
                            raise
            except asyncio.TimeoutError:
                await self.increment_stat("pool_exhaustions")
                raise DatabaseError(
                    f"Timeout acquiring connection from pool '{self.config.pool_name}' "
                    f"after {self.config.connection_timeout}s"
                )

        except DatabaseError:
            await self.increment_stat("pool_misses")
            raise
        except Exception as e:
            await self.increment_stat("pool_misses")
            logger.error(f"Failed to get database connection: {e}")
            raise DatabaseError(f"Failed to acquire database connection: {e}") from e
        finally:
            # Decrement active connections only if the session was acquired (i.e., if active_connections was incremented)
            if success:
                await self.increment_stat("active_connections", -1)

            # Record connection metrics
            wait_time = time.time() - start_time
            await self.update_wait_time(wait_time)

            # Only record success metric if operation succeeded
            if success:
                logger.debug(
                    f"Connection acquired successfully in {wait_time:.3f}s for pool {self.config.pool_name}"
                )
            else:
                logger.debug(
                    f"Connection acquisition failed after {wait_time:.3f}s for pool {self.config.pool_name}"
                )

    async def _close_pool(self) -> None:
        """Close the database connection pool."""
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info(f"Database connection pool '{self.config.pool_name}' closed")
