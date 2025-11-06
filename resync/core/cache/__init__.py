"""
Cache module for the resync system.

This package provides caching functionality including:
- AsyncTTLCache: Main async cache implementation
- BaseCache: Abstract base class for cache implementations
- CacheMemoryManager: Memory management for cache bounds checking
- CachePersistenceManager: Snapshot and restore functionality
- CacheTransactionManager: Transaction support for cache operations
"""

from .async_cache_refactored import AsyncTTLCache
from .base_cache import BaseCache
from .memory_manager import CacheMemoryManager, CacheEntry
from .persistence_manager import CachePersistenceManager
from .transaction_manager import CacheTransactionManager


# Create a basic RobustCacheManager for compatibility
class RobustCacheManager:
    """Basic robust cache manager implementation."""

    def __init__(self, cache_backend=None):
        self.cache_backend = cache_backend or AsyncTTLCache()


__all__ = [
    "AsyncTTLCache",
    "BaseCache",
    "CacheMemoryManager",
    "CacheEntry",
    "CachePersistenceManager",
    "CacheTransactionManager",
    "RobustCacheManager",
]
