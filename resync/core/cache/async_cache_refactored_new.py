"""
Refactored Async TTL Cache Implementation

This module provides a refactored version of AsyncTTLCache that uses extracted components
for better modularity and maintainability while preserving all existing functionality.
"""

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import Any, Dict, List, Optional, Tuple

from resync.core.cache.base_cache import BaseCache
from resync.core.cache.memory_manager import CacheMemoryManager, CacheEntry
from resync.core.cache.persistence_manager import CachePersistenceManager
from resync.core.cache.transaction_manager import CacheTransactionManager
from resync.core.exceptions import CacheError
from resync.core.metrics import log_with_correlation, runtime_metrics
from resync.core.write_ahead_log import WalEntry, WalOperationType, WriteAheadLog

logger = logging.getLogger(__name__)


class AsyncTTLCache(BaseCache):
    """
    Refactored asynchronous TTL cache using extracted components.

    This implementation uses:
    - CacheMemoryManager for memory bounds checking and LRU eviction
    - CachePersistenceManager for snapshot and restore operations
    - CacheTransactionManager for transaction support
    - BaseCache as the abstract base class

    Features maintained from original implementation:
    - Async get() and set() methods for non-blocking operations
    - Thread-safe concurrent access using sharded asyncio.Lock
    - Background cleanup task for expired entries
    - Time-based eviction using asyncio.sleep()
    - Memory bounds checking with intelligent sampling
    - Comprehensive metrics collection and health monitoring
    - Transaction support with rollback capability
    - Snapshot and restore functionality for persistence
    - LRU eviction when cache bounds are exceeded
    - Production-grade error handling and logging
    - Write-Ahead Logging (WAL) support
    """

    def __init__(
        self,
        ttl_seconds: int = 60,
        cleanup_interval: int = 30,
        num_shards: int = 16,
        enable_wal: bool = False,
        wal_path: Optional[str] = None,
        max_entries: int = 100000,
        max_memory_mb: int = 100,
        paranoia_mode: bool = False,
        snapshot_dir: str = "./cache_snapshots",
    ):
        """
        Initialize the refactored async cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
            cleanup_interval: How often to run background cleanup in seconds
            num_shards: Number of shards for the lock
            enable_wal: Whether to enable Write-Ahead Logging for persistence
            wal_path: Path for WAL files (default: cache_wal in current directory)
            max_entries: Maximum number of entries in cache
            max_memory_mb: Maximum memory usage in MB
            paranoia_mode: Enable paranoid operational mode with lower bounds
            snapshot_dir: Directory path for storing snapshot files
        """
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "init",
                "ttl_seconds": ttl_seconds,
                "cleanup_interval": cleanup_interval,
                "num_shards": num_shards,
                "enable_wal": enable_wal,
                "max_entries": max_entries,
                "max_memory_mb": max_memory_mb,
                "paranoia_mode": paranoia_mode,
            }
        )

        try:
            # Load configuration from settings if available
            try:
                from resync.settings import settings

                self.ttl_seconds = (
                    ttl_seconds
                    if ttl_seconds != 60
                    else getattr(settings, "ASYNC_CACHE_TTL", ttl_seconds)
                )
                self.cleanup_interval = (
                    cleanup_interval
                    if cleanup_interval != 30
                    else getattr(
                        settings, "ASYNC_CACHE_CLEANUP_INTERVAL", cleanup_interval
                    )
                )
                self.num_shards = (
                    num_shards
                    if num_shards != 16
                    else getattr(settings, "ASYNC_CACHE_NUM_SHARDS", num_shards)
                )
                # Preserve explicit False values and allow override via settings only
                self.enable_wal = (
                    enable_wal
                    if enable_wal is not False
                    else getattr(settings, "ASYNC_CACHE_ENABLE_WAL", enable_wal)
                )
                self.wal_path = (
                    wal_path
                    if wal_path is not None
                    else getattr(settings, "ASYNC_CACHE_WAL_PATH", wal_path)
                )
                self.max_entries = (
                    max_entries
                    if max_entries != 100000
                    else getattr(settings, "ASYNC_CACHE_MAX_ENTRIES", max_entries)
                )
                self.max_memory_mb = (
                    max_memory_mb
                    if max_memory_mb != 100
                    else getattr(settings, "ASYNC_CACHE_MAX_MEMORY_MB", max_memory_mb)
                )
                self.paranoia_mode = (
                    paranoia_mode
                    if paranoia_mode != False
                    else getattr(settings, "ASYNC_CACHE_PARANOIA_MODE", paranoia_mode)
                )

                log_with_correlation(
                    logging.DEBUG,
                    "Loaded cache config from settings module",
                    correlation_id,
                )
            except ImportError:
                # Handle the case where settings module is not available
                self.ttl_seconds = ttl_seconds
                self.cleanup_interval = cleanup_interval
                self.num_shards = num_shards
                self.enable_wal = enable_wal
                self.wal_path = wal_path
                self.max_entries = max_entries
                self.max_memory_mb = max_memory_mb
                self.paranoia_mode = paranoia_mode
                log_with_correlation(
                    logging.WARNING,
                    "Settings module not available, using provided values or defaults",
                    correlation_id,
                )

            # Apply paranoia mode limits
            if self.paranoia_mode:
                self.max_entries = min(self.max_entries, 10000)
                self.max_memory_mb = min(self.max_memory_mb, 10)

            # Initialize cache shards and locks
            self.shards: List[Dict[str, CacheEntry]] = [
                {} for _ in range(self.num_shards)
            ]
            self.shard_locks = [asyncio.Lock() for _ in range(self.num_shards)]
            self.cleanup_task: Optional[asyncio.Task[None]] = None
            self.is_running = False

            # Initialize component managers
            self.memory_manager = CacheMemoryManager(
                max_entries=self.max_entries,
                max_memory_mb=self.max_memory_mb,
                paranoia_mode=self.paranoia_mode,
            )

            self.persistence_manager = CachePersistenceManager(
                snapshot_dir=snapshot_dir
            )

            self.transaction_manager = CacheTransactionManager()

            # Initialize WAL if enabled
            self.wal: Optional[WriteAheadLog] = None
            if self.enable_wal:
                wal_path_to_use = self.wal_path or "./cache_wal"
                self.wal = WriteAheadLog(wal_path_to_use)
                log_with_correlation(
                    logging.INFO,
                    f"WAL enabled for cache, path: {wal_path_to_use}",
                    correlation_id,
                )

            # Mark for WAL replay if needed
            self._needs_wal_replay_on_first_use = True
            
            # Initialize lock contention metrics
            self._lock_contention_counts = [0] * self.num_shards
            self._lock_acquisition_times = [[] for _ in range(self.num_shards)]

            runtime_metrics.record_health_check(
                "async_cache_refactored",
                "initialized",
                {
                    "ttl_seconds": self.ttl_seconds,
                    "cleanup_interval": self.cleanup_interval,
                    "num_shards": self.num_shards,
                    "enable_wal": self.enable_wal,
                },
            )
            log_with_correlation(
                logging.INFO,
                "AsyncTTLCache (refactored) initialized successfully",
                correlation_id,
            )

        except Exception as e:
            runtime_metrics.record_health_check(
                "async_cache_refactored", "init_failed", {"error": str(e)}
            )
            log_with_correlation(
                logging.CRITICAL,
                f"Failed to initialize AsyncTTLCache (refactored): {e}",
                correlation_id,
            )
            raise
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def _replay_wal_on_startup(self) -> int:
        """
        Replay the WAL log on cache startup to restore state.

        Returns:
            Number of operations replayed
        """
        if not self.enable_wal or not self.wal:
            return 0

        # Replay the WAL to rebuild cache state
        replayed_count = await self.wal.replay_log(self)
        return replayed_count

    def _get_shard(self, key: str) -> Tuple[Dict[str, CacheEntry], asyncio.Lock]:
        """
        Get the shard and lock for a given key with bounds checking.
        
        Returns:
            Tuple containing:
            - shard: The dictionary shard for this key
            - lock: The asyncio.Lock specific to this shard
            
        Note: The lock MUST be used when modifying the shard to ensure thread safety.
        Always use: async with lock: # modify shard
        """
        try:
            key_hash = hash(key)
            if key_hash == 0:
                key_hash = sum(ord(c) for c in str(key)) + len(str(key))

            shard_index = abs(key_hash) % self.num_shards

            if not (0 <= shard_index < self.num_shards):
                shard_index = (len(key) + (ord(key[0]) if key else 0)) % self.num_shards

        except (OverflowError, ValueError) as e:
            key_sum = sum(ord(c) for c in str(key)[:20])
            shard_index = key_sum % self.num_shards
            logger.warning(
                f"Hash computation failed for key {repr(key)}: {e}, using fallback shard {shard_index}"
            )

        return self.shards[shard_index], self.shard_locks[shard_index]
    
    async def _acquire_lock_with_metrics(self, lock: asyncio.Lock, shard_idx: int) -> None:
        """
        Acquire a lock while measuring acquisition time and contention.
        
        Args:
            lock: The asyncio.Lock to acquire
            shard_idx: Index of the shard for metrics tracking
        """
        start_time = time.time()
        
        # Try to acquire lock with a small timeout to detect contention
        try:
            await asyncio.wait_for(lock.acquire(), timeout=0.01)
            acquisition_time = time.time() - start_time
            
            # Record acquisition time
            self._lock_acquisition_times[shard_idx].append(acquisition_time)
            
            # Keep only recent measurements (last 100)
            if len(self._lock_acquisition_times[shard_idx]) > 100:
                self._lock_acquisition_times[shard_idx] = self._lock_acquisition_times[shard_idx][-100:]
            
            # Log contention if acquisition took too long
            if acquisition_time > 0.01:  # 10ms threshold
                self._lock_contention_counts[shard_idx] += 1
                logger.warning(
                    "Lock contention detected on shard %d: acquisition time=%.3fms",
                    shard_idx, acquisition_time * 1000
                )
        except asyncio.TimeoutError:
            # Lock is contended
            self._lock_contention_counts[shard_idx] += 1
            logger.warning("Lock timeout on shard %d, acquiring without timeout", shard_idx)
            await lock.acquire()
    
    async def _release_lock_with_metrics(self, lock: asyncio.Lock) -> None:
        """
        Release a lock previously acquired with _acquire_lock_with_metrics.
        
        Args:
            lock: The asyncio.Lock to release
        """
        lock.release()

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if not self.is_running:
            try:
                asyncio.get_running_loop()
                self.is_running = True
                self.cleanup_task = asyncio.create_task(self._cleanup_expired_entries())
            except RuntimeError:
                pass

    async def _cleanup_expired_entries(self) -> None:
        """Background task to cleanup expired entries."""
        correlation_id = runtime_metrics.create_correlation_id(
            {"component": "async_cache_refactored", "operation": "cleanup_task"}
        )

        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._remove_expired_entries()
                runtime_metrics.cache_cleanup_cycles.increment()
                runtime_metrics.cache_size.set(self.size())

            except asyncio.CancelledError:
                log_with_correlation(
                    logging.DEBUG,
                    "AsyncTTLCache (refactored) cleanup task cancelled",
                    correlation_id,
                )
                break
            except Exception as e:
                log_with_correlation(
                    logging.CRITICAL,
                    f"Unexpected error in AsyncTTLCache (refactored) cleanup task: {e}",
                    correlation_id,
                    exc_info=True,
                )
                raise CacheError(
                    "Unexpected critical error during cache cleanup"
                ) from e

        runtime_metrics.close_correlation_id(correlation_id)

    async def _remove_expired_entries(self) -> None:
        """Remove expired entries from cache using parallel processing."""
        correlation_id = runtime_metrics.create_correlation_id(
            {"component": "async_cache_refactored", "operation": "remove_expired"}
        )

        current_time = time()
        total_removed = 0

        # Function to process a single shard
        async def process_shard(i):
            shard = self.shards[i]
            lock = self.shard_locks[i]
            async with lock:
                expired_keys = [
                    key
                    for key, entry in shard.items()
                    if current_time - entry.timestamp > entry.ttl
                ]
                for key in expired_keys:
                    del shard[key]
                    log_with_correlation(
                        logging.DEBUG,
                        f"Removed expired cache entry: {key}",
                        correlation_id,
                    )
                return len(expired_keys)

        # Process all shards concurrently
        shard_indices = list(range(self.num_shards))
        tasks = [process_shard(i) for i in shard_indices]
        results = await asyncio.gather(*tasks)

        total_removed = sum(results)

        if total_removed > 0:
            runtime_metrics.cache_evictions.increment(total_removed)
            log_with_correlation(
                logging.DEBUG,
                f"Cleaned up {total_removed} expired cache entries",
                correlation_id,
            )

        runtime_metrics.close_correlation_id(correlation_id)

    async def get(self, key: str) -> Optional[Any]:
        """
        Asynchronously retrieve an item from the cache.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "get",
                "key": repr(key),
            }
        )

        # Ensure cleanup task is running
        self._start_cleanup_task()

        # Perform WAL replay if needed on first use
        if (
            hasattr(self, "_needs_wal_replay_on_first_use")
            and self._needs_wal_replay_on_first_use
        ):
            self._needs_wal_replay_on_first_use = False
            replayed_ops = await self._replay_wal_on_startup()
            logger.info(
                "replayed_operations_from_WAL_on_first_use", replayed_ops=replayed_ops
            )

        try:
            # Validate key
            if key is None:
                raise TypeError("Cache key cannot be None")

            key = str(key)
            if len(key) == 0:
                raise ValueError("Cache key cannot be empty")
            if len(key) > 1000:
                raise ValueError(
                    f"Cache key too long: {len(key)} characters (max 1000)"
                )
            if "\x00" in key or "\r" in key or "\n" in key:
                raise ValueError("Cache key cannot contain control characters")

            shard, lock = self._get_shard(key)
            shard_idx = self.shards.index(shard)
            await self._acquire_lock_with_metrics(lock, shard_idx)
            try:
                entry = shard.get(key)
                if entry:
                    current_time = time()
                    if current_time - entry.timestamp <= entry.ttl:
                        runtime_metrics.cache_hits.increment()
                        entry.timestamp = current_time  # Update timestamp for LRU
                        log_with_correlation(
                            logging.DEBUG,
                            f"Cache HIT for key: {repr(key)}",
                            correlation_id,
                        )
                        return entry.data
                    else:
                        # Entry expired, remove it
                        del shard[key]
                        runtime_metrics.cache_evictions.increment()

                runtime_metrics.cache_misses.increment()
                log_with_correlation(
                    logging.DEBUG, f"Cache MISS for key: {repr(key)}", correlation_id
                )
                return None
            except Exception as exc:
                logger.error("Erro ao acessar shard para key=%s", key, exc_info=exc)
                raise
            finally:
                self._release_lock_with_metrics(lock)

        except Exception as e:
            log_with_correlation(
                logging.ERROR,
                f"Cache GET failed for key {repr(key)}: {e}",
                correlation_id,
            )
            raise
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Asynchronously add an item to the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override for this specific entry

        Returns:
            True if successfully stored, False otherwise
        """
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "set",
                "key": repr(key),
                "ttl": ttl,
            }
        )

        # Ensure cleanup task is running
        self._start_cleanup_task()

        # Perform WAL replay if needed on first use
        if (
            hasattr(self, "_needs_wal_replay_on_first_use")
            and self._needs_wal_replay_on_first_use
        ):
            self._needs_wal_replay_on_first_use = False
            replayed_ops = await self._replay_wal_on_startup()
            logger.info(
                "replayed_operations_from_WAL_on_first_use", replayed_ops=replayed_ops
            )

        try:
            # Validate inputs
            key = self._validate_key(key)
            self._validate_value(value)
            ttl_seconds = self._validate_ttl(ttl)

            # WAL logging
            if self.enable_wal and self.wal:
                wal_entry = WalEntry(
                    operation=WalOperationType.SET,
                    key=key,
                    value=value,
                    ttl=ttl_seconds,
                )
                await self.wal.log_operation(wal_entry)

            current_time = time()
            entry = CacheEntry(data=value, timestamp=current_time, ttl=ttl_seconds)

            shard, lock = self._get_shard(key)
            shard_idx = self.shards.index(shard)
            await self._acquire_lock_with_metrics(lock, shard_idx)
            try:
                # Check memory bounds using memory manager
                current_size = sum(len(s) for s in self.shards)
                if not self.memory_manager.check_memory_bounds(
                    self.shards, current_size + 1
                ):
                    # Need to evict entries to make room
                    bytes_freed = self.memory_manager.evict_to_fit(
                        self.shards, self.shard_locks, 0, key
                    )

                shard[key] = entry

                # Final bounds check
                if not self.memory_manager.check_memory_bounds(
                    self.shards, current_size + 1
                ):
                    del shard[key]
                    raise ValueError(
                        f"Cache bounds exceeded: cannot add key {repr(key)}"
                    )

                runtime_metrics.cache_sets.increment()
                runtime_metrics.cache_size.set(self.size())
                log_with_correlation(
                    logging.DEBUG, f"Cache SET for key: {repr(key)}", correlation_id
                )
                return True
            except Exception as exc:
                logger.error("Erro ao atualizar shard para key=%s", key, exc_info=exc)
                raise
            finally:
                self._release_lock_with_metrics(lock)

        except Exception as e:
            log_with_correlation(
                logging.ERROR,
                f"Cache SET failed for key {repr(key)}: {e}",
                correlation_id,
            )
            raise
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def delete(self, key: str) -> bool:
        """
        Asynchronously delete an item from the cache.

        Args:
            key: Cache key to delete

        Returns:
            True if item was deleted, False if not found
        """
        correlation_id = runtime_metrics.create_correlation_id(
            {"component": "async_cache_refactored", "operation": "delete", "key": key}
        )

        try:
            # WAL logging
            if self.enable_wal and self.wal:
                wal_entry = WalEntry(operation=WalOperationType.DELETE, key=key)
                await self.wal.log_operation(wal_entry)

            shard, lock = self._get_shard(key)
            shard_idx = self.shards.index(shard)
            await self._acquire_lock_with_metrics(lock, shard_idx)
            try:
                if key in shard:
                    del shard[key]
                    runtime_metrics.cache_evictions.increment()
                    runtime_metrics.cache_size.set(self.size())
                    log_with_correlation(
                        logging.DEBUG, f"Cache DELETE for key: {key}", correlation_id
                    )
                    return True
                return False
            except Exception as exc:
                logger.error("Erro ao deletar do shard para key=%s", key, exc_info=exc)
                raise
            finally:
                self._release_lock_with_metrics(lock)
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def clear(self) -> None:
        """Asynchronously clear all cache entries."""
        for i in range(self.num_shards):
            shard = self.shards[i]
            lock = self.shard_locks[i]
            async with lock:
                shard.clear()
        logger.debug("Cache CLEARED")

    def size(self) -> int:
        """Get the current number of items in cache."""
        return sum(len(shard) for shard in self.shards)

    def _validate_key(self, key: Any) -> str:
        """Validate the cache key."""
        if key is None:
            raise TypeError("Cache key cannot be None")

        key = str(key)
        if len(key) == 0:
            raise ValueError("Cache key cannot be empty")
        if len(key) > 1000:
            raise ValueError(f"Cache key too long: {len(key)} characters (max 1000)")
        if "\x00" in key or "\r" in key or "\n" in key:
            raise ValueError("Cache key cannot contain control characters")

        return key

    def _validate_value(self, value: Any) -> None:
        """Validate the cache value."""
        if value is None:
            raise ValueError("Cache value cannot be None")

    def _validate_ttl(self, ttl: Optional[int]) -> float:
        """Validate the TTL value."""
        if ttl is None:
            return float(self.ttl_seconds)
        elif not isinstance(ttl, (int, float)):
            raise TypeError(f"TTL must be numeric: {type(ttl)}")
        elif ttl < 0:
            raise ValueError(f"TTL cannot be negative: {ttl}")
        elif ttl > 86400 * 365:
            raise ValueError(f"TTL too large: {ttl} seconds (max 1 year)")

        return float(ttl)

    # Transaction support using CacheTransactionManager
    async def begin_transaction(self, key: str) -> str:
        """Begin a new transaction."""
        return await self.transaction_manager.begin_transaction(key)

    async def commit_transaction(self, transaction_id: str) -> bool:
        """Commit a transaction."""
        return await self.transaction_manager.commit_transaction(transaction_id)

    async def rollback_transaction(self, transaction_id: str) -> bool:
        """Rollback a transaction."""
        return await self.transaction_manager.rollback_transaction(transaction_id)

    # Persistence support using CachePersistenceManager
    def create_backup_snapshot(self) -> str:
        """Create a backup snapshot of cache state."""
        # Convert internal cache format to persistence manager format
        cache_data = {}
        for i, shard in enumerate(self.shards):
            for key, entry in shard.items():
                if f"shard_{i}" not in cache_data:
                    cache_data[f"shard_{i}"] = {}
                cache_data[f"shard_{i}"][key] = {
                    "data": entry.data,
                    "timestamp": entry.timestamp,
                    "ttl": entry.ttl,
                }

        return self.persistence_manager.create_backup_snapshot(cache_data)

    async def restore_from_snapshot(self, snapshot_path: str) -> bool:
        """Restore cache from a snapshot file."""
        try:
            snapshot = self.persistence_manager.restore_from_snapshot(snapshot_path)

            # Clear current cache
            await self.clear()

            # Restore from snapshot
            for shard_key, shard_data in snapshot.items():
                if shard_key.startswith("shard_") and isinstance(shard_data, dict):
                    shard_idx = int(shard_key.split("_")[1])
                    if 0 <= shard_idx < self.num_shards:
                        shard = self.shards[shard_idx]
                        lock = self.shard_locks[shard_idx]

                        await self._acquire_lock_with_metrics(lock, shard_idx)
                        try:
                            for key, entry_data in shard_data.items():
                                entry = CacheEntry(
                                    data=entry_data["data"],
                                    timestamp=entry_data["timestamp"],
                                    ttl=entry_data["ttl"],
                                )
                                shard[key] = entry
                        except Exception as exc:
                            logger.error("Erro ao restaurar shard %d do snapshot", shard_idx, exc_info=exc)
                            raise
                        finally:
                            self._release_lock_with_metrics(lock)

            runtime_metrics.cache_size.set(self.size())
            return True

        except Exception as e:
            logger.error(f"Failed to restore from snapshot {snapshot_path}: {e}")
            return False

    def list_snapshots(self) -> list:
        """List all available snapshots."""
        return self.persistence_manager.list_snapshots()

    def cleanup_old_snapshots(self, max_age_seconds: int = 86400) -> int:
        """Remove snapshots older than the specified age."""
        return self.persistence_manager.cleanup_old_snapshots(max_age_seconds)

    # Health check and monitoring
    def get_hot_shards(self, threshold_percentile: float = 0.8) -> List[int]:
        """
        Identify shards that have significantly more entries than others.
        
        Args:
            threshold_percentile: Percentile threshold (0.0-1.0) to consider a shard "hot"
            
        Returns:
            List of shard indices that are considered hot
        """
        shard_sizes = [len(shard) for shard in self.shards]
        if not shard_sizes:
            return []
        
        # Calculate threshold based on percentile
        import numpy as np
        threshold = np.percentile(shard_sizes, threshold_percentile * 100)
        
        # Identify shards above threshold
        hot_shards = [i for i, size in enumerate(shard_sizes) if size >= threshold]
        
        # Log warning if hot shards detected
        if hot_shards:
            logger.warning(
                "Hot shards detected: %s with sizes: %s",
                hot_shards,
                [shard_sizes[i] for i in hot_shards]
            )
        
        return hot_shards

    def get_detailed_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics for monitoring."""
        total_requests = (
            runtime_metrics.cache_hits.value + runtime_metrics.cache_misses.value
        )
        total_sets = runtime_metrics.cache_sets.value
        total_evictions = runtime_metrics.cache_evictions.value

        return {
            "size": self.size(),
            "num_shards": self.num_shards,
            "ttl_seconds": self.ttl_seconds,
            "cleanup_interval": self.cleanup_interval,
            "hits": runtime_metrics.cache_hits.value,
            "misses": runtime_metrics.cache_misses.value,
            "sets": total_sets,
            "evictions": total_evictions,
            "cleanup_cycles": runtime_metrics.cache_cleanup_cycles.value,
            "hit_rate": (
                (runtime_metrics.cache_hits.value / total_requests)
                if total_requests > 0
                else 0
            ),
            "miss_rate": (
                (runtime_metrics.cache_misses.value / total_requests)
                if total_requests > 0
                else 0
            ),
            "eviction_rate": (total_evictions / total_sets) if total_sets > 0 else 0,
            "shard_distribution": [len(shard) for shard in self.shards],
            "hot_shards": self.get_hot_shards(),
            "lock_contention": {
                "contention_counts": self._lock_contention_counts,
                "avg_acquisition_times": [
                    sum(times) / len(times) if times else 0
                    for times in self._lock_acquisition_times
                ]
            },
            "is_running": self.is_running,
            "health_status": runtime_metrics.get_health_status().get(
                "async_cache_refactored", {}
            ),
            "memory_info": self.memory_manager.get_memory_info(self.shards),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            correlation_id = runtime_metrics.create_correlation_id(
                {"component": "async_cache_refactored", "operation": "health_check"}
            )

            from resync.core import env_detector

            is_production = env_detector.is_production()

            # Basic functionality test
            test_key = f"health_check_{correlation_id.id}_{int(time())}"
            test_value = {"test": "data", "timestamp": time()}

            await self.set(test_key, test_value, 300)
            retrieved = await self.get(test_key)
            if retrieved != test_value:
                return {
                    "status": "critical",
                    "component": "async_cache_refactored",
                    "error": "Functionality test failed",
                    "production_ready": False,
                }

            await self.delete(test_key)

            # Check memory bounds
            current_size = self.size()
            bounds_ok = self.memory_manager.check_memory_bounds(
                self.shards, current_size
            )

            # Check background tasks
            cleanup_status = (
                "running"
                if self.cleanup_task and not self.cleanup_task.done()
                else "stopped"
            )

            result = {
                "status": "healthy",
                "component": "async_cache_refactored",
                "production_ready": True,
                "size": current_size,
                "num_shards": self.num_shards,
                "shard_distribution": [len(shard) for shard in self.shards],
                "cleanup_status": cleanup_status,
                "ttl_seconds": self.ttl_seconds,
                "bounds_compliant": bounds_ok,
                "environment": env_detector._environment,
            }

            log_with_correlation(
                logging.DEBUG,
                f"Cache health check PASSED - production ready: {result['production_ready']}",
                correlation_id,
            )
            runtime_metrics.close_correlation_id(correlation_id)
            return result

        except Exception as e:
            return {
                "status": "critical",
                "component": "async_cache_refactored",
                "error": f"Health check failed: {e}",
                "production_ready": False,
            }

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        self.is_running = False
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.debug("AsyncTTLCache (refactored) stopped")

    async def __aenter__(self) -> "AsyncTTLCache":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - cleanup resources."""
        await self.stop()

    # WAL replay methods
    async def apply_wal_set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Apply a SET operation from WAL replay without re-logging."""
        try:
            validated_key = self._validate_key(key)
            self._validate_value(value)
            validated_ttl = self._validate_ttl(ttl)

            current_time = time()
            entry = CacheEntry(data=value, timestamp=current_time, ttl=validated_ttl)

            shard, lock = self._get_shard(validated_key)
            shard_idx = self.shards.index(shard)
            await self._acquire_lock_with_metrics(lock, shard_idx)
            try:
                # Use memory manager for eviction if needed
                current_size = sum(len(s) for s in self.shards)
                if not self.memory_manager.check_memory_bounds(
                    self.shards, current_size + 1
                ):
                    self.memory_manager.evict_to_fit(
                        self.shards, self.shard_locks, 0, validated_key
                    )

                shard[validated_key] = entry
                runtime_metrics.cache_sets.increment()
                runtime_metrics.cache_size.set(self.size())
            except Exception as exc:
                logger.error("Erro ao aplicar WAL SET para key=%s", validated_key, exc_info=exc)
                raise
            finally:
                self._release_lock_with_metrics(lock)
        except Exception as e:
            logger.error("WAL_replay_SET_failed", key=repr(key), error=str(e))

    async def apply_wal_delete(self, key: str):
        """Apply a DELETE operation from WAL replay without re-logging."""
        try:
            shard, lock = self._get_shard(key)
            shard_idx = self.shards.index(shard)
            await self._acquire_lock_with_metrics(lock, shard_idx)
            try:
                if key in shard:
                    del shard[key]
                    runtime_metrics.cache_evictions.increment()
                    runtime_metrics.cache_size.set(self.size())
            except Exception as exc:
                logger.error("Erro ao aplicar WAL DELETE para key=%s", key, exc_info=exc)
                raise
            finally:
                self._release_lock_with_metrics(lock)
        except Exception as e:
            logger.error("WAL_replay_DELETE_failed", key=key, error=str(e))