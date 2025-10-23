"""
Refactored AsyncTTLCache Implementation

This module provides a refactored version of AsyncTTLCache that uses the Strategy pattern
and extracted manager classes to improve modularity, maintainability, and reduce complexity.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import time
from typing import Any, Dict, List, Optional, Tuple

from resync.core.cache.memory_manager import CacheMemoryManager
from resync.core.cache.persistence_manager import CachePersistenceManager
from resync.core.cache.strategies import (
    CacheEntry,
    CacheRestoreStrategy,
    CacheRollbackStrategy,
    CacheSetStrategy,
    StandardCacheRestoreStrategy,
    StandardCacheRollbackStrategy,
    StandardCacheSetStrategy,
)
from resync.core.cache.transaction_manager import CacheTransactionManager
from resync.core.exceptions import CacheError
from resync.core.metrics import log_with_correlation, runtime_metrics
from resync.core.write_ahead_log import WriteAheadLog

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single entry in the cache with timestamp and TTL."""

    data: Any
    timestamp: float
    ttl: float


class AsyncTTLCache:
    """
    Refactored asynchronous TTL cache using Strategy pattern and extracted managers.

    This version improves upon the original by:
    - Using Strategy pattern for complex operations (set, rollback, restore)
    - Extracting memory management to CacheMemoryManager
    - Extracting persistence to CachePersistenceManager
    - Extracting transaction management to CacheTransactionManager
    - Significantly reducing method complexity from D-rated to A/B-rated
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
    ):
        """
        Initialize the refactored async cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
            cleanup_interval: How often to run background cleanup in seconds
            num_shards: Number of shards for the lock
            enable_wal: Whether to enable Write-Ahead Logging for persistence
            wal_path: Path for WAL files
            max_entries: Maximum number of entries in cache
            max_memory_mb: Maximum memory usage in MB
            paranoia_mode: Enable paranoid operational mode with lower bounds
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
            self._load_configuration(
                ttl_seconds,
                cleanup_interval,
                num_shards,
                enable_wal,
                wal_path,
                max_entries,
                max_memory_mb,
                paranoia_mode,
            )

            # Initialize core data structures
            self.shards: List[Dict[str, CacheEntry]] = [
                {} for _ in range(self.num_shards)
            ]
            self.shard_locks = [asyncio.Lock() for _ in range(self.num_shards)]
            self.cleanup_task: Optional[asyncio.Task[None]] = None
            self.is_running = False

            # Initialize managers
            self.memory_manager = CacheMemoryManager(
                max_entries=self.max_entries,
                max_memory_mb=self.max_memory_mb,
                paranoia_mode=self.paranoia_mode,
            )

            self.persistence_manager = CachePersistenceManager()
            self.transaction_manager = CacheTransactionManager()

            # Initialize strategies
            self.set_strategy: CacheSetStrategy = StandardCacheSetStrategy()
            self.rollback_strategy: CacheRollbackStrategy = (
                StandardCacheRollbackStrategy()
            )
            self.restore_strategy: CacheRestoreStrategy = StandardCacheRestoreStrategy()

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

            # Mark WAL replay as needed if applicable
            self._needs_wal_replay_on_first_use = self.enable_wal and self.wal

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
                "Refactored AsyncTTLCache initialized successfully",
                correlation_id,
            )

        except Exception as e:
            runtime_metrics.record_health_check(
                "async_cache_refactored", "init_failed", {"error": str(e)}
            )
            log_with_correlation(
                logging.CRITICAL,
                f"Failed to initialize Refactored AsyncTTLCache: {e}",
                correlation_id,
            )
            raise
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    def _load_configuration(
        self,
        ttl_seconds: int,
        cleanup_interval: int,
        num_shards: int,
        enable_wal: bool,
        wal_path: Optional[str],
        max_entries: int,
        max_memory_mb: int,
        paranoia_mode: bool,
    ) -> None:
        """Load configuration from settings or use provided defaults."""
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
                else getattr(settings, "ASYNC_CACHE_CLEANUP_INTERVAL", cleanup_interval)
            )
            self.num_shards = (
                num_shards
                if num_shards != 16
                else getattr(settings, "ASYNC_CACHE_NUM_SHARDS", num_shards)
            )
            self.enable_wal = (
                enable_wal
                if enable_wal != False
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
                runtime_metrics.create_correlation_id(
                    {"component": "async_cache_refactored"}
                ),
            )
        except ImportError:
            # Use provided values if settings module not available
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
                runtime_metrics.create_correlation_id(
                    {"component": "async_cache_refactored"}
                ),
            )

        # Apply paranoia mode adjustments
        if self.paranoia_mode:
            self.max_entries = min(self.max_entries, 10000)
            self.max_memory_mb = min(self.max_memory_mb, 10)

    async def _replay_wal_on_startup(self) -> int:
        """Replay the WAL log on cache startup to restore state."""
        if not self.enable_wal or not self.wal:
            return 0

        replayed_count = await self.wal.replay_log(self)
        return replayed_count

    def _get_shard(self, key: str) -> Tuple[Dict[str, CacheEntry], asyncio.Lock]:
        """Get the shard and lock for a given key with bounds checking."""
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

    def _get_lru_key(self, shard: Dict[str, CacheEntry]) -> Optional[str]:
        """Get the least recently used key in a shard."""
        if not shard:
            return None

        lru_key = min(shard.keys(), key=lambda k: shard[k].timestamp)
        return lru_key

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
                    "Refactored AsyncTTLCache cleanup task cancelled",
                    correlation_id,
                )
                break
            except Exception as e:
                log_with_correlation(
                    logging.CRITICAL,
                    f"Unexpected error in Refactored AsyncTTLCache cleanup task: {e}",
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

        # Process all shards concurrently
        async def process_shard(i: int) -> int:
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
                return len(expired_keys)

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

    async def get(self, key: Any) -> Any | None:
        """Asynchronously retrieve an item from the cache."""
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "get",
                "key": repr(key),
            }
        )

        self._start_cleanup_task()

        if self._needs_wal_replay_on_first_use:
            self._needs_wal_replay_on_first_use = False
            await self._replay_wal_on_startup()

        try:
            # Validate and normalize key
            validated_key = self._validate_key(key)

            shard, lock = self._get_shard(validated_key)
            async with lock:
                entry = shard.get(validated_key)
                if entry:
                    current_time = time()
                    if current_time - entry.timestamp <= entry.ttl:
                        runtime_metrics.cache_hits.increment()
                        entry.timestamp = current_time  # Update for LRU
                        return entry.data

                    # Entry expired
                    del shard[validated_key]
                    runtime_metrics.cache_evictions.increment()

                runtime_metrics.cache_misses.increment()
                return None

        except Exception as e:
            log_with_correlation(
                logging.ERROR,
                f"Cache GET failed for key {repr(key)}: {e}",
                correlation_id,
            )
            raise
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def set(
        self, key: str, value: Any, ttl_seconds: Optional[float] = None
    ) -> None:
        """Asynchronously add an item to the cache using the set strategy."""
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "set",
                "key": repr(key),
                "ttl_seconds": ttl_seconds,
            }
        )

        self._start_cleanup_task()

        if self._needs_wal_replay_on_first_use:
            self._needs_wal_replay_on_first_use = False
            await self._replay_wal_on_startup()

        try:
            # Validate inputs
            validated_key, validated_ttl = self._validate_set_inputs(
                key, value, ttl_seconds
            )

            # Use strategy pattern for complex set operation
            await self.set_strategy.execute(
                key=validated_key,
                value=value,
                ttl_seconds=validated_ttl,
                shards=self.shards,
                shard_locks=self.shard_locks,
                memory_manager=self.memory_manager,
                enable_wal=self.enable_wal,
                wal=self.wal,
            )

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
        """Asynchronously delete an item from the cache."""
        correlation_id = runtime_metrics.create_correlation_id(
            {"component": "async_cache_refactored", "operation": "delete", "key": key}
        )

        if self._needs_wal_replay_on_first_use:
            self._needs_wal_replay_on_first_use = False
            await self._replay_wal_on_startup()

        try:
            if self.enable_wal and self.wal:
                from resync.core.write_ahead_log import WalEntry, WalOperationType

                wal_entry = WalEntry(operation=WalOperationType.DELETE, key=key)
                await self.wal.log_operation(wal_entry)

            shard, lock = self._get_shard(key)
            async with lock:
                if key in shard:
                    del shard[key]
                    runtime_metrics.cache_evictions.increment()
                    runtime_metrics.cache_size.set(self.size())
                    return True
                return False
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def rollback_transaction(self, operations: List[Dict[str, Any]]) -> bool:
        """Rollback cache operations using the rollback strategy."""
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "rollback",
                "operations_count": len(operations),
            }
        )

        try:
            # Use strategy pattern for complex rollback operation
            return await self.rollback_strategy.execute(
                operations=operations,
                shards=self.shards,
                shard_locks=self.shard_locks,
                default_ttl=self.ttl_seconds,
            )

        except Exception as e:
            log_with_correlation(
                logging.ERROR,
                f"Cache rollback failed: {e}",
                correlation_id,
                exc_info=True,
            )
            return False
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def clear(self) -> None:
        """Asynchronously clear all cache entries."""
        for i in range(self.num_shards):
            shard = self.shards[i]
            lock = self.shard_locks[i]
            async with lock:
                shard.clear()

    def size(self) -> int:
        """Get the current number of items in cache."""
        return sum(len(shard) for shard in self.shards)

    def _validate_key(self, key: Any) -> str:
        """Validate and normalize cache key."""
        if key is None:
            raise TypeError("Cache key cannot be None")

        if not isinstance(key, (str, int, float, bool)):
            try:
                str_key = str(key)
                if len(str_key) > 1000:
                    raise ValueError(
                        f"Cache key too long: {len(str_key)} characters (max 1000)"
                    )
                if "\x00" in str_key:
                    raise ValueError("Cache key cannot contain null bytes")
                key = str_key
            except Exception:
                raise TypeError(f"Cache key must be convertible to string: {type(key)}")
        else:
            key = str(key)

        if len(key) == 0:
            raise ValueError("Cache key cannot be empty")
        if len(key) > 1000:
            raise ValueError(f"Cache key too long: {len(key)} characters (max 1000)")
        if "\x00" in key or "\r" in key or "\n" in key:
            raise ValueError("Cache key cannot contain control characters")

        return key

    def _validate_set_inputs(
        self, key: Any, value: Any, ttl_seconds: Optional[float]
    ) -> Tuple[str, float]:
        """Validate inputs for set operation."""
        validated_key = self._validate_key(key)

        if value is None:
            raise ValueError("Cache value cannot be None")

        validated_ttl = self._validate_ttl(ttl_seconds)
        return validated_key, validated_ttl

    def _validate_ttl(self, ttl_seconds: Optional[float]) -> float:
        """Validate TTL value."""
        if ttl_seconds is None:
            return self.ttl_seconds
        elif not isinstance(ttl_seconds, (int, float)):
            raise TypeError(f"TTL must be numeric: {type(ttl_seconds)}")
        elif ttl_seconds < 0:
            raise ValueError(f"TTL cannot be negative: {ttl_seconds}")
        elif ttl_seconds > 86400 * 365:
            raise ValueError(f"TTL too large: {ttl_seconds} seconds (max 1 year)")

        return ttl_seconds

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
            "is_running": self.is_running,
            "health_status": runtime_metrics.get_health_status().get(
                "async_cache_refactored", {}
            ),
        }

    def create_backup_snapshot(self) -> Dict[str, Any]:
        """Create a backup snapshot of current cache state."""
        correlation_id = runtime_metrics.create_correlation_id(
            {"component": "async_cache_refactored", "operation": "backup_snapshot"}
        )

        try:
            snapshot = {}
            current_time = time()

            for shard_idx, shard in enumerate(self.shards):
                shard_snapshot = {}
                for key, entry in shard.items():
                    if current_time - entry.timestamp <= entry.ttl:
                        shard_snapshot[key] = {
                            "data": entry.data,
                            "timestamp": entry.timestamp,
                            "ttl": entry.ttl,
                        }
                snapshot[f"shard_{shard_idx}"] = shard_snapshot

            snapshot["_metadata"] = {
                "created_at": current_time,
                "total_entries": sum(
                    len(s) for s in snapshot.values() if isinstance(s, dict)
                ),
                "correlation_id": correlation_id,
            }

            log_with_correlation(
                logging.INFO,
                f"Created cache backup snapshot with {snapshot['_metadata']['total_entries']} entries",
                correlation_id,
            )
            return snapshot

        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """Restore cache from snapshot using the restore strategy."""
        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "async_cache_refactored",
                "operation": "restore_snapshot",
                "snapshot_entries": snapshot.get("_metadata", {}).get(
                    "total_entries", 0
                ),
            }
        )

        try:
            # Use strategy pattern for complex restore operation
            return await self.restore_strategy.execute(
                snapshot=snapshot,
                shards=self.shards,
                shard_locks=self.shard_locks,
                max_entries=self.max_entries,
            )

        except Exception as e:
            log_with_correlation(
                logging.ERROR,
                f"Failed to restore from snapshot: {e}",
                correlation_id,
                exc_info=True,
            )
            return False
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        self.is_running = False
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            correlation_id = runtime_metrics.create_correlation_id(
                {"component": "async_cache_refactored", "operation": "health_check"}
            )

            from resync.core import env_detector

            is_production = env_detector.is_production()

            # Test basic functionality
            test_key = f"health_check_{correlation_id.id}_{int(time())}"
            test_value = {"test": "data", "timestamp": time()}

            await self.set(test_key, test_value, ttl_seconds=300)
            retrieved = await self.get(test_key)
            if retrieved != test_value:
                return {
                    "status": "critical",
                    "component": "async_cache_refactored",
                    "error": "Health check data mismatch",
                    "production_ready": False,
                }

            await self.delete(test_key)

            # Get comprehensive metrics
            metrics = self.get_detailed_metrics()

            return {
                "status": "healthy",
                "component": "async_cache_refactored",
                "production_ready": True,
                "size": metrics["size"],
                "num_shards": metrics["num_shards"],
                "shard_distribution": metrics["shard_distribution"],
                "cleanup_status": (
                    "running"
                    if self.cleanup_task and not self.cleanup_task.done()
                    else "stopped"
                ),
                "ttl_seconds": metrics["ttl_seconds"],
                "hit_rate": metrics["hit_rate"],
                "environment": env_detector._environment,
            }

        except Exception as e:
            return {
                "status": "critical",
                "component": "async_cache_refactored",
                "error": f"Health check failed: {e}",
                "production_ready": False,
            }

    async def __aenter__(self) -> "AsyncTTLCache":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()

    # WAL replay methods
    async def apply_wal_set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Apply a SET operation from WAL replay."""
        try:
            validated_key, validated_ttl = self._validate_set_inputs(key, value, ttl)

            await self.set_strategy.execute(
                key=validated_key,
                value=value,
                ttl_seconds=validated_ttl,
                shards=self.shards,
                shard_locks=self.shard_locks,
                memory_manager=self.memory_manager,
                enable_wal=False,  # Don't re-log during replay
                wal=None,
            )
        except Exception as e:
            logger.error("WAL_replay_SET_failed", key=repr(key), error=str(e))

    async def apply_wal_delete(self, key: str):
        """Apply a DELETE operation from WAL replay."""
        try:
            shard, lock = self._get_shard(key)
            async with lock:
                if key in shard:
                    del shard[key]
                    runtime_metrics.cache_evictions.increment()
                    runtime_metrics.cache_size.set(self.size())
        except Exception as e:
            logger.error("WAL_replay_DELETE_failed", key=key, error=str(e))
