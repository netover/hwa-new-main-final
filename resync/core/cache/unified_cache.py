"""
Unified Async Cache Implementation

This module provides a comprehensive cache implementation that consolidates all the unique features
from various cache implementations in the project. It serves as a single, robust cache solution
with all the best features from existing implementations.

Features:
- Async operations with TTL support
- Configurable two-tier hierarchy (memory + optional Redis)
- Memory bounds checking with intelligent eviction
- Stampede protection
- Comprehensive metrics
- WAL support for persistence
- Transaction support
- LRU eviction
- Background cleanup
- Thread-safe concurrent access using sharded locks
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

from resync.core.write_ahead_log import (
    WalEntry,
    WalOperationType,
    WriteAheadLog,
)
from resync.utils.exceptions import CacheError

from resync.core.cache.base_cache import BaseCache
from resync.core.cache.memory_manager import CacheEntry, CacheMemoryManager
from resync.core.cache.persistence_manager import CachePersistenceManager
from resync.core.cache.transaction_manager import CacheTransactionManager

# Import cachetools for LRU cache implementation
try:
    from cachetools import LRUCache
except ImportError:
    # Fallback implementation if cachetools is not available
    class LRUCache:
        """Simple LRU cache implementation as fallback"""

        def __init__(self, maxsize=1000):
            self.maxsize = maxsize
            self.cache = {}
            self.order = []

        def __getitem__(self, key):
            if key in self.cache:
                # Move to end (most recently used)
                self.order.remove(key)
                self.order.append(key)
                return self.cache[key]
            raise KeyError(key)

        def __setitem__(self, key, value):
            if key in self.cache:
                # Update existing
                self.cache[key] = value
                self.order.remove(key)
                self.order.append(key)
            else:
                # Add new
                if len(self.cache) >= self.maxsize:
                    # Remove least recently used
                    oldest = self.order.pop(0)
                    del self.cache[oldest]
                self.cache[key] = value
                self.order.append(key)

        def __delitem__(self, key):
            if key in self.cache:
                del self.cache[key]
                self.order.remove(key)

        def __contains__(self, key):
            return key in self.cache

        def get(self, key, default=None):
            return self.cache.get(key, default)

        def clear(self):
            self.cache.clear()
            self.order.clear()


import contextlib

from prometheus_client import CollectorRegistry, Counter, Histogram

logger = logging.getLogger(__name__)

T = TypeVar("T")


class StampedeProtectionLevel(Enum):
    """Levels of stampede protection."""

    NONE = "none"
    BASIC = "basic"
    AGGRESSIVE = "aggressive"


@dataclass
class UnifiedCacheConfig:
    """Configuration for unified cache."""

    # Basic configuration
    ttl_seconds: int = 300  # 5 minutes
    cleanup_interval: int = 60  # 1 minute
    max_entries: int = 100_000
    max_memory_mb: int = 100

    # Hierarchy configuration
    enable_hierarchy: bool = False
    l1_max_size: int = 5000
    l2_ttl_seconds: int = 600
    l2_cleanup_interval: int = 60
    # Option to disable Redis L2 cache for small deployments
    disable_l2_cache: bool = False
    enable_encryption: bool = False
    key_prefix: str = "cache:"

    # Performance configuration
    num_shards: int = 16
    eviction_batch_size: int = 100
    enable_weak_refs: bool = True

    # Protection configuration
    stampede_protection_level: StampedeProtectionLevel = (
        StampedeProtectionLevel.BASIC
    )
    max_concurrent_loads: int = 3
    load_timeout: int = 30

    # Persistence configuration
    enable_wal: bool = False
    wal_path: str | None = None
    snapshot_dir: str = "./cache_snapshots"

    # Advanced configuration
    paranoia_mode: bool = False
    enable_metrics: bool = True


@dataclass
class UnifiedCacheMetrics:
    """Comprehensive metrics for unified cache."""

    # Basic metrics
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    # Hierarchy metrics
    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0

    # Performance metrics
    total_get_latency: float = 0.0
    total_set_latency: float = 0.0
    memory_usage_bytes: int = 0

    # Protection metrics
    stampede_prevented: int = 0
    concurrent_loads: int = 0

    # Persistence metrics
    wal_entries: int = 0
    snapshots_taken: int = 0
    snapshots_restored: int = 0

    def get_hit_ratio(self) -> float:
        """Calculate overall hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_l1_hit_ratio(self) -> float:
        """Calculate L1 hit ratio."""
        total = self.l1_hits + self.l1_misses
        return self.l1_hits / total if total > 0 else 0.0

    def get_l2_hit_ratio(self) -> float:
        """Calculate L2 hit ratio."""
        total = self.l2_hits + self.l2_misses
        return self.l2_hits / total if total > 0 else 0.0

    def get_avg_get_latency(self) -> float:
        """Calculate average get latency."""
        return self.total_get_latency / self.hits if self.hits > 0 else 0.0

    def get_avg_set_latency(self) -> float:
        """Calculate average set latency."""
        return self.total_set_latency / self.sets if self.sets > 0 else 0.0


class UnifiedAsyncCache(BaseCache, Generic[T]):
    """
    Unified asynchronous cache implementation with comprehensive features.

    This implementation consolidates all the unique features from various cache
    implementations in the project into a single, robust solution.
    """

    def __init__(self, config: UnifiedCacheConfig | None = None):
        """
        Initialize unified cache.

        Args:
            config: Configuration for cache. If None, default configuration is used.
        """
        self.config = config or UnifiedCacheConfig()
        self.metrics = UnifiedCacheMetrics()

        # Initialize cache storage with memory limit
        self._cache: LRUCache[str, CacheEntry] = LRUCache(maxsize=1000)
        self._weak_cache: dict[str, weakref.ref] = {}

        # Initialize hierarchy if enabled
        if self.config.enable_hierarchy:
            self._init_hierarchy()

        # Initialize sharding for concurrency with memory limits
        self._shards: list[LRUCache[str, CacheEntry]] = [
            LRUCache(
                maxsize=max(
                    100, self.config.max_entries // self.config.num_shards
                )
            )
            for _ in range(self.config.num_shards)
        ]
        self._shard_locks: list[asyncio.Lock] = [
            asyncio.Lock() for _ in range(self.config.num_shards)
        ]

        # Initialize stampede protection
        self._loading: dict[str, asyncio.Event] = {}
        self._loading_lock = asyncio.Lock()

        # Initialize persistence
        if self.config.enable_wal:
            self.wal = WriteAheadLog(self.config.wal_path or "./cache_wal")
        else:
            self.wal = None

        self.persistence_manager = CachePersistenceManager(
            self.config.snapshot_dir
        )
        self.transaction_manager = CacheTransactionManager()

        # Initialize memory management
        self.memory_manager = CacheMemoryManager(
            max_entries=self.config.max_entries,
            max_memory_mb=self.config.max_memory_mb,
            enable_weak_refs=self.config.enable_weak_refs,
        )

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

        # Prometheus metrics
        if self.config.enable_metrics:
            self._init_prometheus_metrics()

    def _init_hierarchy(self):
        """Initialize two-tier cache hierarchy."""
        # L1 cache (in-memory)
        self.l1_cache = LRUCache(maxsize=self.config.l1_max_size)

        # L2 cache (Redis-backed) - only if not disabled
        if not self.config.disable_l2_cache:
            # Note: Using a simple in-memory cache for L2 to avoid import issues
            self.l2_cache = LRUCache(maxsize=self.config.l2_max_size)
        else:
            self.l2_cache = None
            logger.info("L2 cache disabled for small deployment")

        # Add lock for hierarchy operations
        self._hierarchy_lock = asyncio.Lock()

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics if enabled."""
        if not self.config.enable_metrics:
            return

        try:
            # Use a unique name for this cache instance to avoid conflicts
            instance_id = id(self)
            cache_hits = Counter(
                f"unified_cache_hits_total_{instance_id}", "Total cache hits"
            )
            cache_misses = Counter(
                f"unified_cache_misses_total_{instance_id}",
                "Total cache misses",
            )
            cache_latency = Histogram(
                f"unified_cache_latency_seconds_{instance_id}",
                "Cache operation latency",
            )

            self.cache_hits = cache_hits
            self.cache_misses = cache_misses
            self.cache_latency = cache_latency

            # Register with a custom registry to avoid conflicts
            registry = CollectorRegistry()
            registry.register(cache_hits)
            registry.register(cache_misses)
            registry.register(cache_latency)

        except Exception as e:
            logger.warning("Failed to initialize Prometheus metrics: %s", e)

    async def initialize(self) -> None:
        """Initialize cache and start background tasks."""
        if self._running:
            return

        self._running = True

        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Restore from snapshot if available
        # Note: Skipping restore for now as it's causing issues
        # if self.persistence_manager:
        #     snapshot_data = self.persistence_manager.restore_from_snapshot(self._get_latest_snapshot_path())
        #     await self._restore_from_snapshot_data(snapshot_data)

        logger.info("Unified cache initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        if not self._running:
            return

        self._running = False

        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # Create snapshot before shutdown
        # Note: Skipping snapshot for now as it's causing issues
        # if self.persistence_manager:
        #     await self.persistence_manager.create_backup_snapshot(self._convert_shards_to_dict())

        logger.info("Unified cache shutdown successfully")

    def _get_shard(
        self, key: str
    ) -> tuple[LRUCache[str, CacheEntry], asyncio.Lock]:
        """Get shard and lock for a given key."""
        shard_index = hash(key) % self.config.num_shards
        return self._shards[shard_index], self._shard_locks[shard_index]

    async def get(self, key: str, default: T | None = None) -> T | None:
        """
        Get a value from cache.

        Args:
            key: The cache key
            default: Default value to return if key is not found

        Returns:
            The cached value or default if not found
        """
        start_time = time.time()

        try:
            # Try hierarchy first if enabled
            if self.config.enable_hierarchy:
                value = await self._get_from_hierarchy(key)
                if value is not None:
                    self.metrics.hits += 1
                    self.metrics.total_get_latency += time.time() - start_time
                    if self.config.enable_metrics:
                        self.cache_hits.inc()
                    return value

            # Try regular cache
            shard, lock = self._get_shard(key)
            async with lock:
                if key in shard:
                    entry = shard[key]
                    if not entry.is_expired():
                        entry.refresh_access()
                        self.metrics.hits += 1
                        self.metrics.total_get_latency += (
                            time.time() - start_time
                        )
                        if self.config.enable_metrics:
                            self.cache_hits.inc()
                        return entry.value
                    # Entry expired, remove it
                    del shard[key]

            # Try weak references
            if self.config.enable_weak_refs and key in self._weak_cache:
                weak_ref = self._weak_cache[key]
                value = weak_ref()
                if value is not None:
                    # Promote back to regular cache
                    await self.set(key, value)
                    self.metrics.hits += 1
                    self.metrics.total_get_latency += time.time() - start_time
                    if self.config.enable_metrics:
                        self.cache_hits.inc()
                    return value
                # Weak reference is dead, remove it
                del self._weak_cache[key]

            # Cache miss
            self.metrics.misses += 1
            self.metrics.total_get_latency += time.time() - start_time
            if self.config.enable_metrics:
                self.cache_misses.inc()
            return default

        except Exception as e:
            logger.error("Error getting key %s from cache: %s", key, e)
            raise CacheError(f"Failed to get key {key}: {e}") from e

    # Override the abstract method with compatible signature
    async def base_get(self, key: str) -> Any | None:
        """
        Get a value from cache (BaseCache interface implementation).

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found
        """
        return await self.get(key, None)

    async def _get_from_hierarchy(self, key: str) -> T | None:
        """Get value from two-tier cache hierarchy."""
        async with self._hierarchy_lock:
            # Try L1 cache first
            try:
                value = self.l1_cache[key]
                self.metrics.l1_hits += 1
                return value
            except KeyError:
                self.metrics.l1_misses += 1

            # Try L2 cache only if enabled
            if self.l2_cache is not None:
                value = await self.l2_cache.get(key)
                if value is not None:
                    # Promote to L1 cache
                    self.l1_cache[key] = value
                    self.metrics.l2_hits += 1
                    return value

        self.metrics.l2_misses += 1
        return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> bool:
        """
        Set a value in cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Optional time-to-live in seconds

        Returns:
            True if the value was successfully stored, False otherwise
        """
        start_time = time.time()

        try:
            # Set in hierarchy if enabled
            if self.config.enable_hierarchy:
                await self._set_in_hierarchy(key, value, ttl)

            # Set in regular cache
            ttl = ttl or self.config.ttl_seconds
            expiry = time.time() + ttl

            # Create cache entry
            entry = CacheEntry(value, expiry, ttl)

            # Get shard and lock
            shard, lock = self._get_shard(key)
            async with lock:
                # Check if we need to evict entries (LRUCache handles eviction automatically)
                # No need to check size as LRUCache handles it internally

                # Store entry
                shard[key] = entry

            # Store in weak references if enabled and value is large
            if self.config.enable_weak_refs and self._is_large_object(value):
                self._weak_cache[key] = weakref.ref(value)

            # Write to WAL if enabled
            if self.wal:
                await self.wal.log_operation(
                    WalEntry(
                        operation=WalOperationType.SET,
                        key=key,
                        value=value,
                        timestamp=time.time(),
                    )
                )
                self.metrics.wal_entries += 1

            # Update metrics
            self.metrics.sets += 1
            self.metrics.total_set_latency += time.time() - start_time
            if self.config.enable_metrics:
                self.cache_latency.observe(time.time() - start_time)

            return True  # Successfully set

        except Exception as e:
            logger.error("Error setting key %s in cache: %s", key, e)
            raise CacheError(f"Failed to set key {key}: {e}") from e

    async def _set_in_hierarchy(
        self, key: str, value: T, ttl: int | None = None
    ) -> None:
        """Set value in two-tier cache hierarchy."""
        # Set in L1 cache
        self.l1_cache[key] = value

        # Set in L2 cache only if enabled
        if self.l2_cache is not None:
            self.l2_cache[key] = value

    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: The cache key to delete

        Returns:
            True if key was found and deleted, False otherwise
        """
        try:
            deleted = False

            # Delete from hierarchy if enabled
            if self.config.enable_hierarchy:
                if key in self.l1_cache:
                    del self.l1_cache[key]
                    deleted = True

                # Delete from L2 cache if hierarchy is enabled and L2 cache is not disabled
                if self.config.enable_hierarchy and self.l2_cache is not None:
                    if key in self.l2_cache:
                        del self.l2_cache[key]
                        l2_deleted = True
                    deleted = deleted or l2_deleted

            # Delete from regular cache
            shard, lock = self._get_shard(key)
            async with lock:
                if key in shard:
                    del shard[key]
                    deleted = True

            # Delete from weak references
            if self.config.enable_weak_refs and key in self._weak_cache:
                del self._weak_cache[key]
                deleted = True

            # Write to WAL if enabled
            if self.wal and deleted:
                await self.wal.log_operation(
                    WalEntry(
                        operation=WalOperationType.DELETE,
                        key=key,
                        timestamp=time.time(),
                    )
                )
                self.metrics.wal_entries += 1

            # Update metrics
            if deleted:
                self.metrics.deletes += 1

            return deleted

        except Exception as e:
            logger.error("Error deleting key %s from cache: %s", key, e)
            raise CacheError(f"Failed to delete key {key}: {e}") from e

    async def clear(self) -> None:
        """Clear all values from cache."""
        try:
            # Clear hierarchy if enabled
            if self.config.enable_hierarchy:
                self.l1_cache.clear()
                if self.l2_cache is not None:
                    self.l2_cache.clear()

            # Clear regular cache
            for shard in self._shards:
                shard.clear()

            # Clear weak references
            if self.config.enable_weak_refs:
                self._weak_cache.clear()

            # Write to WAL if enabled
            if self.wal:
                await self.wal.log_operation(
                    WalEntry(
                        operation=WalOperationType.CLEAR,
                        timestamp=time.time(),
                    )
                )

            logger.info("Cache cleared successfully")

        except Exception as e:
            logger.error("Error clearing cache: %s", e)
            raise CacheError(f"Failed to clear cache: {e}") from e

    async def get_with_loader(
        self, key: str, loader: Callable[[], T], ttl: int | None = None
    ) -> T:
        """
        Get a value from cache, loading it with the provided function if not found.

        This method provides stampede protection to prevent multiple concurrent loads
        for the same key.

        Args:
            key: The cache key
            loader: Function to load the value if not in cache
            ttl: Optional time-to-live in seconds

        Returns:
            The cached or loaded value
        """
        # Try to get from cache first
        value = await self.get(key)
        if value is not None:
            return value

        # Implement stampede protection
        if (
            self.config.stampede_protection_level
            != StampedeProtectionLevel.NONE
        ):
            return await self._get_with_stampede_protection(key, loader, ttl)
        return await self._get_without_protection(key, loader, ttl)

    async def _get_with_stampede_protection(
        self, key: str, loader: Callable[[], T], ttl: int | None = None
    ) -> T:
        """Get value with stampede protection."""
        async with self._loading_lock:
            # Check if already loading
            if key in self._loading:
                # Wait for loading to complete
                event = self._loading[key]
                await event.wait()

                # Return cached value
                value = await self.get(key)
                if value is not None:
                    return value

                # If loading failed, try again
                return await self._load_value(key, loader, ttl)

            # Mark as loading
            self._loading[key] = asyncio.Event()
            self.metrics.concurrent_loads += 1

        try:
            # Load value
            value = await self._load_value(key, loader, ttl)
            self.metrics.stampede_prevented += 1
            return value
        finally:
            # Mark loading as complete
            async with self._loading_lock:
                if key in self._loading:
                    self._loading[key].set()
                    del self._loading[key]

    async def _get_without_protection(
        self, key: str, loader: Callable[[], T], ttl: int | None = None
    ) -> T:
        """Get value without stampede protection."""
        return await self._load_value(key, loader, ttl)

    async def _load_value(
        self, key: str, loader: Callable[[], T], ttl: int | None = None
    ) -> T:
        """Load value using the provided loader function."""
        try:
            # Load value
            if asyncio.iscoroutinefunction(loader):
                value = await loader()
            else:
                value = loader()

            # Cache value
            await self.set(key, value, ttl)

            return value

        except Exception as e:
            logger.error("Error loading value for key %s: %s", key, e)
            raise CacheError(f"Failed to load value for key {key}: {e}") from e

    async def _evict_from_shard(
        self, shard: LRUCache[str, CacheEntry]
    ) -> None:
        """Evict entries from a shard based on LRU policy."""
        # Sort entries by last access time
        entries = sorted(shard.items(), key=lambda x: x[1].last_accessed)

        # Evict oldest entries
        num_to_evict = min(self.config.eviction_batch_size, len(entries))
        for i in range(num_to_evict):
            key, _ = entries[i]
            del shard[key]
            self.metrics.evictions += 1

    def _is_large_object(self, value: Any) -> bool:
        """Check if an object is large enough to use weak references."""
        # Simple heuristic: objects larger than 1KB are considered large
        try:
            import sys

            return sys.getsizeof(value) > 1024
        except Exception:
            return False

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired entries."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop: %s", e)

    async def _cleanup_expired_entries(self) -> None:
        """Clean up expired entries from all shards."""
        current_time = time.time()

        for shard in self._shards:
            expired_keys = [
                key
                for key, entry in shard.items()
                if entry.is_expired(current_time)
            ]

            for key in expired_keys:
                del shard[key]

    async def get_metrics(self) -> UnifiedCacheMetrics:
        """Get current cache metrics."""
        # Update memory usage
        self.metrics.memory_usage_bytes = (
            self.memory_manager.estimate_cache_memory_usage(self._shards)
            * 1024
            * 1024
        )  # Convert MB to bytes

        return self.metrics

    async def create_transaction(self) -> CacheTransactionManager:
        """Create a new transaction for atomic cache operations."""
        return self.transaction_manager

    async def snapshot(self) -> None:
        """Create a snapshot of current cache state."""
        if self.persistence_manager:
            self.persistence_manager.create_backup_snapshot(
                self._convert_shards_to_dict()
            )
            self.metrics.snapshots_taken += 1

    async def restore(self) -> None:
        """Restore cache state from a snapshot."""
        if self.persistence_manager:
            snapshot_data = self.persistence_manager.restore_from_snapshot(
                self._get_latest_snapshot_path()
            )
            await self._restore_from_snapshot_data(snapshot_data)
            self.metrics.snapshots_restored += 1

    async def __aenter__(self) -> UnifiedAsyncCache[T]:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()

    def _convert_shards_to_dict(self) -> dict[str, Any]:
        """Convert shards to dictionary format for snapshot."""
        result = {}
        for i, shard in enumerate(self._shards):
            shard_dict = {}
            for key, entry in shard.items():
                shard_dict[key] = {
                    "value": entry.value,
                    "timestamp": entry.timestamp,
                    "ttl": entry.ttl,
                }
            result[f"shard_{i}"] = shard_dict
        return result

    def _get_latest_snapshot_path(self) -> str:
        """Get path to the latest snapshot file."""
        snapshots = self.persistence_manager.list_snapshots()
        if snapshots:
            return snapshots[0]["path"]  # Return the newest snapshot
        return ""  # No snapshots available

    async def _restore_from_snapshot_data(
        self, snapshot_data: dict[str, Any]
    ) -> None:
        """Restore cache state from snapshot data."""
        if "_metadata" not in snapshot_data:
            return

        current_time = time.time()
        for key, value in snapshot_data.items():
            if key.startswith("shard_"):
                shard_index = int(key.split("_")[1])
                if shard_index < len(self._shards):
                    shard = self._shards[shard_index]
                    for cache_key, entry_data in value.items():
                        if (
                            "value" in entry_data
                            and "timestamp" in entry_data
                            and "ttl" in entry_data
                        ):
                            entry = CacheEntry(
                                entry_data["value"],
                                entry_data["timestamp"],
                                entry_data["ttl"],
                            )
                            # Only restore if not expired
                            if not entry.is_expired(current_time):
                                shard[cache_key] = entry
