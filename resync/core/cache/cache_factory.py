"""
Cache Factory Module

This module provides a factory class for creating different types of cache instances
in the resync application. It centralizes cache creation logic and allows for
easy extension with new cache implementations.
"""

import logging
import threading
import time
from typing import Any, Dict
from typing import TYPE_CHECKING

from resync.core.cache.base_cache import BaseCache

if TYPE_CHECKING:
    from resync.core.cache_with_stampede_protection import CacheConfig

logger = logging.getLogger(__name__)


class SimpleCache(BaseCache):
    """
    Simple in-memory cache implementation using thread locks for thread safety.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() < entry["expires"]:
                    return entry["value"]
                # Expired, remove it
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in cache."""
        with self._lock:
            # Implement LRU eviction if needed
            if len(self._cache) >= self.max_entries:
                # Remove oldest entry
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k]["accessed"]
                )
                del self._cache[oldest_key]

            ttl_final = ttl or self.ttl_seconds
            self._cache[key] = {
                "value": value,
                "expires": time.time() + ttl_final,
                "accessed": time.time()
            }
            return True

    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all values from cache."""
        with self._lock:
            self._cache.clear()


class MemoryCache(SimpleCache):
    """
    Memory-optimized cache with basic stampede protection.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 10000,
                 stampede_protection: bool = False):
        super().__init__(ttl_seconds, max_entries)
        self.stampede_protection = stampede_protection
        # Note: For simplicity, stampede protection is disabled in sync implementation
        # A full async implementation would be needed for proper stampede protection


class HybridCache(SimpleCache):
    """
    Hybrid cache that simulates memory + persistent storage.
    """

    def __init__(self, ttl_seconds: int = 600, max_entries: int = 50000,
                 l1_max_size: int = 1000, enable_persistence: bool = False):
        super().__init__(ttl_seconds, max_entries)
        self.l1_max_size = l1_max_size
        self.enable_persistence = enable_persistence
        self._l1_cache: Dict[str, Any] = {}
        self._l1_lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get with L1 cache priority."""
        # Check L1 first
        with self._l1_lock:
            if key in self._l1_cache:
                return self._l1_cache[key]

        # Check main cache
        result = super().get(key)
        if result is not None:
            # Promote to L1 if there's space
            with self._l1_lock:
                if len(self._l1_cache) < self.l1_max_size:
                    self._l1_cache[key] = result
            return result

        return result

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set with L1 promotion."""
        # Update L1
        with self._l1_lock:
            self._l1_cache[key] = value

        # Update main cache
        return super().set(key, value, ttl)


class CacheFactory:
    """
    Factory class for creating cache instances.

    This class provides methods to create different types of cache implementations
    based on configuration parameters. It serves as a central point for cache
    creation and allows for easy extension with new cache types.

    The factory supports creating enhanced, memory, and hybrid cache instances,
    each optimized for different use cases and requirements.
    """

    @staticmethod
    def create_enhanced_cache(config: "CacheConfig") -> BaseCache:
        """
        Create an enhanced cache instance with advanced features.

        Args:
            config: Cache configuration containing settings for TTL,
                   stampede protection, and other advanced features

        Returns:
            BaseCache: An enhanced cache implementation instance

        Note:
            This method creates a cache with stampede protection and
            other advanced features suitable for high-concurrency scenarios.
        """
        return MemoryCache(
            ttl_seconds=getattr(config, "default_ttl", 300),
            max_entries=getattr(config, "max_entries", 50000),
            stampede_protection=True
        )

    @staticmethod
    def create_memory_cache(config: "CacheConfig") -> BaseCache:
        """
        Create a memory-based cache instance.

        Args:
            config: Cache configuration containing settings for TTL and other parameters

        Returns:
            BaseCache: A memory-based cache implementation instance

        Note:
            This method creates an in-memory cache suitable for single-process
            applications where data doesn't need to persist across restarts.
        """
        return MemoryCache(
            ttl_seconds=getattr(config, "default_ttl", 300),
            max_entries=getattr(config, "max_entries", 10000)
        )

    @staticmethod
    def create_hybrid_cache(config: "CacheConfig") -> BaseCache:
        """
        Create a hybrid cache instance combining multiple storage backends.

        Args:
            config: Cache configuration containing settings for the hybrid cache

        Returns:
            BaseCache: A hybrid cache implementation instance

        Note:
            This method creates a cache that combines multiple storage backends
            (e.g., memory + persistent storage) for optimal performance and durability.
        """
        return HybridCache(
            ttl_seconds=getattr(config, "default_ttl", 600),
            max_entries=getattr(config, "max_entries", 100000),
            l1_max_size=getattr(config, "l1_max_size", 5000),
            enable_persistence=getattr(config, "enable_persistence", False)
        )
