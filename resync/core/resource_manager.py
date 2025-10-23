"""
Resource Management Utilities for Phase 2 Performance Optimizations.

This module provides utilities for deterministic resource cleanup,
resource tracking, and leak detection following best practices from
Java's try-with-resources and Python's context managers.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ResourceInfo:
    """Information about a managed resource."""

    resource_id: str
    resource_type: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_lifetime_seconds(self) -> float:
        """Get the lifetime of the resource in seconds."""
        return (datetime.now() - self.created_at).total_seconds()


class ManagedResource:
    """
    Base class for managed resources with automatic cleanup.

    Provides deterministic cleanup similar to Java's try-with-resources.
    """

    def __init__(self, resource_id: str, resource_type: str):
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.created_at = datetime.now()
        self._closed = False

    async def __aenter__(self):
        """Async context manager entry."""
        logger.debug(f"Acquiring resource: {self.resource_id} ({self.resource_type})")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        await self.close()
        return False

    def __enter__(self):
        """Sync context manager entry."""
        logger.debug(f"Acquiring resource: {self.resource_id} ({self.resource_type})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit with automatic cleanup."""
        self.close_sync()
        return False

    async def close(self) -> None:
        """Close the resource asynchronously."""
        if not self._closed:
            try:
                await self._cleanup()
                self._closed = True
                lifetime = (datetime.now() - self.created_at).total_seconds()
                logger.debug(
                    f"Closed resource: {self.resource_id} ({self.resource_type}), "
                    f"lifetime: {lifetime:.2f}s"
                )
            except Exception as e:
                logger.error(f"Error closing resource {self.resource_id}: {e}")
                raise

    def close_sync(self) -> None:
        """Close the resource synchronously."""
        if not self._closed:
            try:
                self._cleanup_sync()
                self._closed = True
                lifetime = (datetime.now() - self.created_at).total_seconds()
                logger.debug(
                    f"Closed resource: {self.resource_id} ({self.resource_type}), "
                    f"lifetime: {lifetime:.2f}s"
                )
            except Exception as e:
                logger.error(f"Error closing resource {self.resource_id}: {e}")
                raise

    async def _cleanup(self) -> None:
        """Override this method to implement async cleanup logic."""

    def _cleanup_sync(self) -> None:
        """Override this method to implement sync cleanup logic."""


class DatabaseConnectionResource(ManagedResource):
    """Managed database connection resource."""

    def __init__(self, connection: Any, resource_id: str = "db_connection"):
        super().__init__(resource_id, "database_connection")
        self.connection = connection

    async def _cleanup(self) -> None:
        """Close the database connection."""
        if hasattr(self.connection, "close"):
            if asyncio.iscoroutinefunction(self.connection.close):
                await self.connection.close()
            else:
                self.connection.close()


class FileResource(ManagedResource):
    """Managed file resource."""

    def __init__(self, file_handle: Any, resource_id: str = "file"):
        super().__init__(resource_id, "file")
        self.file_handle = file_handle

    async def _cleanup(self) -> None:
        """Close the file handle."""
        if hasattr(self.file_handle, "close"):
            if asyncio.iscoroutinefunction(self.file_handle.close):
                await self.file_handle.close()
            else:
                self.file_handle.close()

    def _cleanup_sync(self) -> None:
        """Close the file handle synchronously."""
        if hasattr(self.file_handle, "close"):
            self.file_handle.close()


class NetworkSocketResource(ManagedResource):
    """Managed network socket resource."""

    def __init__(self, socket: Any, resource_id: str = "socket"):
        super().__init__(resource_id, "network_socket")
        self.socket = socket

    async def _cleanup(self) -> None:
        """Close the network socket."""
        if hasattr(self.socket, "close"):
            if asyncio.iscoroutinefunction(self.socket.close):
                await self.socket.close()
            else:
                self.socket.close()


@asynccontextmanager
async def managed_database_connection(pool: Any) -> AsyncIterator[Any]:
    """
    Context manager for database connections with automatic cleanup.

    Usage:
        async with managed_database_connection(pool) as conn:
            # Use connection
            result = await conn.execute(query)
        # Connection automatically returned to pool
    """
    try:
        async with pool.get_connection() as conn:
            yield conn
    finally:
        # Connection is automatically returned to pool by the pool's context manager
        pass


@asynccontextmanager
async def managed_file(file_path: str, mode: str = "r") -> AsyncIterator[Any]:
    """
    Context manager for file operations with automatic cleanup.

    Usage:
        async with managed_file('data.txt', 'r') as f:
            content = await f.read()
        # File automatically closed
    """
    # Soft import for aiofiles (optional dependency)
    try:
        import aiofiles  # type: ignore
    except ImportError:
        aiofiles = None  # type: ignore

    if aiofiles is None:
        raise RuntimeError("aiofiles is required for async file operations but is not installed.")

    file_handle = None
    try:
        file_handle = await aiofiles.open(file_path, mode)
        yield file_handle
    finally:
        if file_handle:
            await file_handle.close()


@contextmanager
def managed_file_sync(file_path: str, mode: str = "r") -> Iterator[Any]:
    """
    Synchronous context manager for file operations with automatic cleanup.

    Usage:
        with managed_file_sync('data.txt', 'r') as f:
            content = f.read()
        # File automatically closed
    """
    file_handle = None
    try:
        file_handle = open(file_path, mode)
        yield file_handle
    finally:
        if file_handle:
            file_handle.close()


class ResourcePool:
    """
    Generic resource pool with automatic cleanup and leak detection.

    Features:
    - Resource lifecycle management
    - Automatic cleanup on context exit
    - Leak detection
    - Resource usage tracking
    """

    def __init__(self, max_resources: int = 100):
        self.max_resources = max_resources
        self.active_resources: Dict[str, ResourceInfo] = {}
        self._lock = asyncio.Lock()
        self._resource_counter = 0

    async def acquire(
        self,
        resource_type: str,
        factory: Callable[[], Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Any]:
        """
        Acquire a resource from the pool.

        Args:
            resource_type: Type of resource being acquired
            factory: Factory function to create the resource
            metadata: Optional metadata about the resource

        Returns:
            Tuple of (resource_id, resource)
        """
        async with self._lock:
            if len(self.active_resources) >= self.max_resources:
                raise RuntimeError(
                    f"Resource pool exhausted: {len(self.active_resources)}/{self.max_resources}"
                )

            self._resource_counter += 1
            resource_id = f"{resource_type}_{self._resource_counter}"

            # Create the resource
            if asyncio.iscoroutinefunction(factory):
                resource = await factory()
            else:
                resource = factory()

            # Track the resource
            info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type,
                metadata=metadata or {},
            )
            self.active_resources[resource_id] = info

            logger.debug(f"Acquired resource: {resource_id} ({resource_type})")
            return resource_id, resource

    async def release(self, resource_id: str, resource: Any) -> None:
        """
        Release a resource back to the pool.

        Args:
            resource_id: ID of the resource to release
            resource: The resource object
        """
        async with self._lock:
            if resource_id in self.active_resources:
                info = self.active_resources[resource_id]
                lifetime = info.get_lifetime_seconds()

                # Cleanup the resource
                try:
                    if hasattr(resource, "close"):
                        if asyncio.iscoroutinefunction(resource.close):
                            await resource.close()
                        else:
                            resource.close()
                except Exception as e:
                    logger.error(f"Error closing resource {resource_id}: {e}")

                del self.active_resources[resource_id]
                logger.debug(
                    f"Released resource: {resource_id} ({info.resource_type}), "
                    f"lifetime: {lifetime:.2f}s"
                )

    async def cleanup_all(self) -> None:
        """Cleanup all active resources."""
        async with self._lock:
            for resource_id in list(self.active_resources.keys()):
                info = self.active_resources[resource_id]
                logger.warning(
                    f"Force cleaning up resource: {resource_id} ({info.resource_type})"
                )
                del self.active_resources[resource_id]

    async def detect_leaks(
        self, max_lifetime_seconds: int = 3600
    ) -> List[ResourceInfo]:
        """
        Detect potential resource leaks.

        Args:
            max_lifetime_seconds: Maximum expected resource lifetime

        Returns:
            List of ResourceInfo for potentially leaked resources
        """
        async with self._lock:
            leaks = []
            for info in self.active_resources.values():
                if info.get_lifetime_seconds() > max_lifetime_seconds:
                    leaks.append(info)
                    logger.warning(
                        f"Potential resource leak: {info.resource_id} ({info.resource_type}), "
                        f"lifetime: {info.get_lifetime_seconds():.2f}s"
                    )
            return leaks

    def get_stats(self) -> Dict[str, Any]:
        """Get resource pool statistics."""
        return {
            "active_resources": len(self.active_resources),
            "max_resources": self.max_resources,
            "utilization": len(self.active_resources) / self.max_resources * 100,
            "resource_types": {
                info.resource_type: sum(
                    1
                    for i in self.active_resources.values()
                    if i.resource_type == info.resource_type
                )
                for info in self.active_resources.values()
            },
        }


@asynccontextmanager
async def resource_scope(
    pool: ResourcePool,
    resource_type: str,
    factory: Callable[[], Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[Any]:
    """
    Context manager for scoped resource management.

    Automatically acquires and releases resources from a pool.

    Usage:
        async with resource_scope(pool, 'database', create_connection) as conn:
            # Use connection
            result = await conn.execute(query)
        # Connection automatically released
    """
    resource_id, resource = await pool.acquire(resource_type, factory, metadata)
    try:
        yield resource
    finally:
        await pool.release(resource_id, resource)


class BatchResourceManager:
    """
    Manager for batch resource operations with automatic cleanup.

    Useful for operations that need multiple resources simultaneously.
    """

    def __init__(self):
        self.resources: List[tuple[str, Any, Callable]] = []

    async def add_resource(
        self, resource_id: str, resource: Any, cleanup_fn: Optional[Callable] = None
    ) -> None:
        """Add a resource to the batch."""
        self.resources.append((resource_id, resource, cleanup_fn))
        logger.debug(f"Added resource to batch: {resource_id}")

    async def cleanup_all(self) -> None:
        """Cleanup all resources in the batch."""
        for resource_id, resource, cleanup_fn in reversed(self.resources):
            try:
                if cleanup_fn:
                    if asyncio.iscoroutinefunction(cleanup_fn):
                        await cleanup_fn(resource)
                    else:
                        cleanup_fn(resource)
                elif hasattr(resource, "close"):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()

                logger.debug(f"Cleaned up batch resource: {resource_id}")
            except Exception as e:
                logger.error(f"Error cleaning up batch resource {resource_id}: {e}")

        self.resources.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        await self.cleanup_all()
        return False


# Global resource pool instance
_global_resource_pool: Optional[ResourcePool] = None


def get_global_resource_pool() -> ResourcePool:
    """Get the global resource pool instance."""
    global _global_resource_pool
    if _global_resource_pool is None:
        _global_resource_pool = ResourcePool(max_resources=1000)
    return _global_resource_pool
