"""
Robust Cache Manager with advanced memory management and eviction strategies.

This module provides a comprehensive cache implementation with:
- Memory bounds checking
- LRU (Least Recently Used) eviction
- Configurable size and memory limits
- Comprehensive metrics collection
- Background cleanup task
"""

import asyncio
import logging
import sys
import weakref
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, TypeVar

from resync.core.write_ahead_log import WalEntry, WalOperationType, WriteAheadLog

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheEntry:
    """
    Represents a single cache entry with metadata for tracking and eviction.
    """

    def __init__(self, value: Any, size: int, ttl: Optional[timedelta] = None):
        """
        Initialize a cache entry with tracking metadata.

        Args:
            value: The cached value
            size: Memory size of the entry
            ttl: Optional time-to-live for the entry
        """
        self.value = value
        self.size = size
        self.created_at = datetime.utcnow()
        self.last_accessed = self.created_at
        self.access_count = 0
        self.ttl = ttl

    def is_expired(self) -> bool:
        """
        Check if the entry has expired based on its TTL.

        Returns:
            bool: True if entry is expired, False otherwise
        """
        if self.ttl is None:
            return False
        return datetime.utcnow() - self.created_at > self.ttl

    def refresh_access(self):
        """Update access metadata when entry is accessed."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


class RobustCacheManager:
    """
    Advanced cache manager with comprehensive memory and performance management.

    Features:
    - Accurate deep size calculation
    - LRU eviction
    - TTL support
    - Weak references for large objects
    - Background cleanup
    - Comprehensive metrics
    """

    def __init__(
        self,
        max_items: int = 100_000,
        max_memory_mb: int = 100,
        eviction_batch_size: int = 100,
        enable_weak_refs: bool = True,
        enable_wal: bool = False,
        wal_path: Optional[str] = None,
    ):
        """
        Initialize the robust cache manager.

        Args:
            max_items: Maximum number of items in cache
            max_memory_mb: Maximum memory usage in MB
            eviction_batch_size: Number of items to evict in one batch
            enable_weak_refs: Use weak references for large objects
            enable_wal: Enable Write-Ahead Logging
            wal_path: Path for WAL files
        """
        # Cache storage and management
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._weak_cache: Dict[str, weakref.ref] = {}

        # Configuration parameters
        self.max_items = max_items
        self.max_memory = max_memory_mb * 1024 * 1024
        self.eviction_batch_size = eviction_batch_size
        self.enable_weak_refs = enable_weak_refs

        # Memory tracking
        self._current_memory = 0
        self._lock = asyncio.Lock()

        # Metrics tracking
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._oom_events = 0

        # Write-Ahead Logging
        self.enable_wal = enable_wal
        self.wal: Optional[WriteAheadLog] = None
        if enable_wal:
            self.wal = WriteAheadLog(wal_path or "./cache_wal")

        # Start background cleanup
        asyncio.create_task(self._cleanup_loop())

    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> bool:
        """
        Set a cache entry with comprehensive validation and memory management.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional time-to-live for the entry

        Returns:
            bool: True if entry was successfully cached, False otherwise
        """
        async with self._lock:
            # Calculate item size
            item_size = self._calculate_deep_size(value)

            # Handle oversized items
            if item_size > self.max_memory:
                logger.warning(
                    f"Item size ({item_size / 1024 / 1024:.2f}MB) exceeds "
                    f"max cache memory ({self.max_memory / 1024 / 1024:.2f}MB)"
                )

                if self.enable_weak_refs:
                    self._weak_cache[key] = weakref.ref(value)
                    return True
                else:
                    return False

            # Prepare WAL entry if enabled
            if self.enable_wal and self.wal:
                wal_entry = WalEntry(
                    operation=WalOperationType.SET,
                    key=key,
                    value=value,
                    ttl=ttl.total_seconds() if ttl else None,
                )
                await self.wal.log_operation(wal_entry)

            # Evict entries if necessary
            await self._evict_to_fit(item_size)

            # Create cache entry
            entry = CacheEntry(value, item_size, ttl)

            # Update cache
            if key in self._cache:
                old_size = self._cache[key].size
                self._current_memory -= old_size

            self._cache[key] = entry
            self._cache.move_to_end(key)
            self._current_memory += item_size

            return True

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a cache entry with comprehensive validation.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            # Check weak references first
            if key in self._weak_cache:
                weak_ref = self._weak_cache[key]
                value = weak_ref()

                if value is None:
                    del self._weak_cache[key]
                    self._misses += 1
                    return None

                self._hits += 1
                return value

            # Check main cache
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired():
                await self._remove_entry(key)
                self._misses += 1
                return None

            # Update access metadata
            entry.refresh_access()
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.value

    async def _evict_to_fit(self, required_memory: int):
        """
        Evict cache entries to make space for a new entry.

        Args:
            required_memory: Memory space needed
        """
        target_memory = self.max_memory - required_memory
        evicted_count = 0

        while (
            (len(self._cache) > 0)
            and (
                len(self._cache) >= self.max_items
                or self._current_memory > target_memory
            )
            and evicted_count < self.eviction_batch_size
        ):
            key, entry = self._cache.popitem(last=False)
            self._current_memory -= entry.size
            evicted_count += 1
            self._evictions += 1

        if evicted_count > 0:
            logger.debug(
                f"Evicted {evicted_count} items. "
                f"Memory: {self._current_memory / 1024 / 1024:.2f}MB / "
                f"{self.max_memory / 1024 / 1024:.2f}MB"
            )

    async def _remove_entry(self, key: str):
        """
        Remove a single entry from the cache.

        Args:
            key: Cache key to remove
        """
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_memory -= entry.size

    async def _cleanup_loop(self, interval: int = 60):
        """
        Background task to clean up expired and unnecessary entries.

        Args:
            interval: Cleanup interval in seconds
        """
        while True:
            try:
                await asyncio.sleep(interval)

                async with self._lock:
                    # Remove expired entries
                    expired_keys = [
                        key for key, entry in self._cache.items() if entry.is_expired()
                    ]

                    for key in expired_keys:
                        if key in self._cache:
                            await self._remove_entry(key)

                    # Clean weak references
                    dead_refs = [
                        key for key, ref in self._weak_cache.items() if ref() is None
                    ]

                    for key in dead_refs:
                        del self._weak_cache[key]

            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}", exc_info=True)

    def _calculate_deep_size(self, obj: Any) -> int:
        """
        Calculate the deep memory size of an object.

        Args:
            obj: Object to calculate size for

        Returns:
            Estimated memory size in bytes
        """
        seen = set()

        def _sizeof(obj):
            obj_id = id(obj)

            if obj_id in seen:
                return 0

            seen.add(obj_id)
            size = sys.getsizeof(obj)

            if isinstance(obj, dict):
                size += sum(_sizeof(k) + _sizeof(v) for k, v in obj.items())
            elif isinstance(obj, (list, tuple, set, frozenset)):
                size += sum(_sizeof(item) for item in obj)
            elif hasattr(obj, "__dict__"):
                size += _sizeof(obj.__dict__)
            elif hasattr(obj, "__slots__"):
                size += sum(
                    _sizeof(getattr(obj, attr))
                    for attr in obj.__slots__
                    if hasattr(obj, attr)
                )

            return size

        return _sizeof(obj)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache metrics.

        Returns:
            Dictionary of cache performance metrics
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "items": len(self._cache),
            "memory_mb": self._current_memory / 1024 / 1024,
            "max_memory_mb": self.max_memory / 1024 / 1024,
            "memory_utilization": self._current_memory / self.max_memory,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "weak_refs": len(self._weak_cache),
        }
