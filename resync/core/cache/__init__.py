"""
Cache module for the resync system.

This package provides caching functionality including:
- UnifiedAsyncCache: Main unified cache implementation with all features (if available)
- BaseCache: Abstract base class for cache implementations
- CacheMemoryManager: Memory management for cache bounds checking
- CachePersistenceManager: Snapshot and restore functionality
- CacheTransactionManager: Transaction support for cache operations
- CacheFactory: Factory for creating different cache configurations
"""

import asyncio
import logging
from typing import Optional

from .base_cache import BaseCache
from .cache_factory import CacheFactory, SimpleCache, MemoryCache, HybridCache
from .memory_manager import CacheEntry, CacheMemoryManager
from .persistence_manager import CachePersistenceManager
from .transaction_manager import CacheTransactionManager

# Try to import unified cache classes, but don't fail if dependencies are missing
try:
    from .unified_cache import (
        StampedeProtectionLevel,
        UnifiedAsyncCache,
        UnifiedCacheConfig,
        UnifiedCacheMetrics,
    )
    _UNIFIED_CACHE_AVAILABLE = True
except ImportError as e:
    # Unified cache dependencies are missing, create mock classes
    logger = logging.getLogger(__name__)
    logger.warning("Unified cache not available due to missing dependencies: %s", e)

    # Provide stub classes so imports don't fail
    class StampedeProtectionLevel:
        """Enumeration for cache stampede protection levels."""
        NONE = "none"
        BASIC = "basic"
        AGGRESSIVE = "aggressive"

    class UnifiedCacheConfig:
        """Configuration class for unified cache settings."""

        def __init__(self, **kwargs):
            """Initialize cache configuration with provided keyword arguments."""
            for key, value in kwargs.items():
                setattr(self, key, value)

    class UnifiedCacheMetrics:
        """Metrics collection class for unified cache performance monitoring."""

    class UnifiedAsyncCache(BaseCache):
        """Stub implementation of UnifiedAsyncCache when dependencies are unavailable."""

        def __init__(self, config=None):
            """Initialize the unified async cache with optional configuration."""
            self.config = config or UnifiedCacheConfig()

        def get(self, key: str):
            """Get value from cache (not implemented in stub)."""
            raise NotImplementedError("Unified cache not available")

        def set(self, key: str, value, ttl: Optional[int] = None):
            """Set value in cache with optional TTL (not implemented in stub)."""
            raise NotImplementedError("Unified cache not available")

        def delete(self, key: str) -> bool:
            """Delete value from cache (not implemented in stub)."""
            raise NotImplementedError("Unified cache not available")

        def clear(self):
            """Clear all values from cache (not implemented in stub)."""
            raise NotImplementedError("Unified cache not available")

    _UNIFIED_CACHE_AVAILABLE = False


# Create a basic RobustCacheManager for compatibility
class RobustCacheManager:
    """Basic robust cache manager implementation."""

    def __init__(self, cache_backend=None):
        if cache_backend is None:
            # Try to use unified cache if available, otherwise use simple cache
            try:
                if _UNIFIED_CACHE_AVAILABLE:
                    cache_backend = UnifiedAsyncCache()
                else:
                    cache_backend = SimpleCache()
            except (ImportError, AttributeError, TypeError):
                cache_backend = SimpleCache()
        self.cache_backend = cache_backend

    async def get(self, key: str, default=None):
        """Get value from cache."""
        if hasattr(self.cache_backend, 'get'):
            if hasattr(self.cache_backend.get, '__call__'):
                if asyncio.iscoroutinefunction(self.cache_backend.get):
                    return await self.cache_backend.get(key, default)
                return self.cache_backend.get(key)
        return default

    async def set(self, key: str, value, ttl=None):
        """Set value in cache."""
        if hasattr(self.cache_backend, 'set') and hasattr(self.cache_backend.set, '__call__'):
            if asyncio.iscoroutinefunction(self.cache_backend.set):
                return await self.cache_backend.set(key, value, ttl)
            return self.cache_backend.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if hasattr(self.cache_backend, 'delete') and hasattr(self.cache_backend.delete, '__call__'):
            if asyncio.iscoroutinefunction(self.cache_backend.delete):
                return await self.cache_backend.delete(key)
            return self.cache_backend.delete(key)
        return False

    async def clear(self):
        """Clear all values from cache."""
        if hasattr(self.cache_backend, 'clear') and hasattr(self.cache_backend.clear, '__call__'):
            if asyncio.iscoroutinefunction(self.cache_backend.clear):
                await self.cache_backend.clear()
            self.cache_backend.clear()


__all__ = [
    "UnifiedAsyncCache",
    "UnifiedCacheConfig",
    "StampedeProtectionLevel",
    "UnifiedCacheMetrics",
    "BaseCache",
    "CacheMemoryManager",
    "CacheEntry",
    "CachePersistenceManager",
    "CacheTransactionManager",
    "CacheFactory",
    "SimpleCache",
    "MemoryCache",
    "HybridCache",
    "RobustCacheManager",
]
