"""
Global Resource Manager

This module provides centralized resource management functionality
for connections, pools, and other system resources.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from dataclasses import dataclass
from datetime import datetime
import asyncio
import threading


class ResourcePool(Protocol):
    """Protocol for resource pools."""

    def acquire(self) -> Any:
        """Acquire a resource from the pool."""
        ...

    def release(self, resource: Any) -> None:
        """Release a resource back to the pool."""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        ...


@dataclass
class ResourceStats:
    """Statistics for resource usage."""

    total_resources: int
    available_resources: int
    in_use_resources: int
    waiting_requests: int
    created_at: datetime
    last_used: Optional[datetime] = None


class GlobalResourcePool:
    """
    Global resource pool manager that coordinates multiple resource pools.

    This class manages various types of resources including database connections,
    HTTP clients, cache connections, and other system resources.
    """

    def __init__(self):
        self.pools: Dict[str, ResourcePool] = {}
        self.stats: Dict[str, ResourceStats] = {}
        self.lock = threading.Lock()
        self._initialized = False

    def register_pool(self, name: str, pool: ResourcePool) -> None:
        """
        Register a resource pool.

        Args:
            name: Unique name for the pool
            pool: Resource pool instance
        """
        with self.lock:
            self.pools[name] = pool
            self.stats[name] = ResourceStats(
                total_resources=0,
                available_resources=0,
                in_use_resources=0,
                waiting_requests=0,
                created_at=datetime.now()
            )

    def unregister_pool(self, name: str) -> bool:
        """
        Unregister a resource pool.

        Args:
            name: Name of the pool to unregister

        Returns:
            True if pool was unregistered, False if not found
        """
        with self.lock:
            if name in self.pools:
                del self.pools[name]
                del self.stats[name]
                return True
            return False

    def get_pool(self, name: str) -> Optional[ResourcePool]:
        """
        Get a resource pool by name.

        Args:
            name: Name of the pool

        Returns:
            Resource pool instance or None if not found
        """
        return self.pools.get(name)

    def get_resource_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all resource pools.

        Returns:
            Dictionary of pool statistics
        """
        with self.lock:
            result = {}
            for name, pool in self.pools.items():
                try:
                    pool_stats = pool.get_stats()
                    stats = self.stats[name]
                    result[name] = {
                        "pool_stats": pool_stats,
                        "manager_stats": {
                            "total_resources": stats.total_resources,
                            "available_resources": stats.available_resources,
                            "in_use_resources": stats.in_use_resources,
                            "waiting_requests": stats.waiting_requests,
                            "created_at": stats.created_at.isoformat(),
                            "last_used": stats.last_used.isoformat() if stats.last_used else None,
                        }
                    }
                except Exception as e:
                    result[name] = {"error": str(e)}
            return result

    def optimize_resources(self) -> Dict[str, Any]:
        """
        Perform resource optimization across all pools.

        Returns:
            Optimization results
        """
        optimizations = []
        total_saved = 0

        with self.lock:
            for name, pool in self.pools.items():
                try:
                    # This would contain pool-specific optimization logic
                    # For now, just collect stats
                    stats = pool.get_stats()
                    if stats.get('idle_resources', 0) > 10:
                        optimizations.append(f"Pool {name} has idle resources that could be reduced")
                except Exception as e:
                    optimizations.append(f"Error optimizing pool {name}: {e}")

        return {
            "optimizations": optimizations,
            "resources_saved": total_saved,
            "timestamp": datetime.now().isoformat()
        }

    def health_check(self) -> Dict[str, bool]:
        """
        Perform health check on all resource pools.

        Returns:
            Dictionary mapping pool names to health status
        """
        health_status = {}

        for name, pool in self.pools.items():
            try:
                # Basic health check - try to get stats
                pool.get_stats()
                health_status[name] = True
            except Exception:
                health_status[name] = False

        return health_status

    async def cleanup_idle_resources(self) -> None:
        """
        Clean up idle resources across all pools.
        """
        for pool in self.pools.values():
            try:
                # This would contain cleanup logic for each pool type
                # For now, just a placeholder
                pass
            except Exception:
                # Log error but continue with other pools
                pass


# Global resource pool instance
_global_resource_pool = GlobalResourcePool()


def get_global_resource_pool() -> GlobalResourcePool:
    """
    Get the global resource pool instance.

    Returns:
        GlobalResourcePool instance
    """
    return _global_resource_pool


# Initialize some basic pools if they exist
def _initialize_default_pools():
    """Initialize default resource pools."""
    try:
        # Try to import and register known pools
        from resync.core.pools.redis_pool import RedisPool
        pool = RedisPool()
        _global_resource_pool.register_pool("redis", pool)
    except ImportError:
        pass

    try:
        from resync.core.pools.pool_manager import get_connection_pool_manager
        pool_manager = get_connection_pool_manager()
        _global_resource_pool.register_pool("connections", pool_manager)
    except ImportError:
        pass


# Initialize pools on import
_initialize_default_pools()
