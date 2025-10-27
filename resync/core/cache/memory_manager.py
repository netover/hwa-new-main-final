"""
Memory management functionality for the async cache system.

This module provides the CacheMemoryManager class that handles memory bounds checking
and intelligent eviction strategies for the async cache implementation.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from resync_new.core.monitoring.metrics import runtime_metrics

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a single entry in the cache with timestamp and TTL."""

    def __init__(self, data: Any, timestamp: float, ttl: float):
        self.data = data
        self.timestamp = timestamp
        self.ttl = ttl
        self.value = data  # Add value attribute for direct access

    def is_expired(self, current_time: float | None = None) -> bool:
        """
        Check if the cache entry has expired.

        Args:
            current_time: Current time to check against. If None, uses time.time()

        Returns:
            True if the entry has expired, False otherwise
        """
        if current_time is None:
            current_time = time.time()

        return current_time > (self.timestamp + self.ttl)

    def refresh_access(self) -> None:
        """
        Refresh the access timestamp for the cache entry.

        This method is called when the entry is accessed to update
        the last access time for LRU eviction calculations.
        """
        self.timestamp = time.time()


class CacheMemoryManager:
    """
    Manages memory bounds and eviction strategies for the async cache.

    This class provides centralized memory management functionality including:
    - Memory usage estimation and bounds checking
    - LRU-based eviction strategies
    - Memory-aware cache sizing decisions

    The memory manager works with sharded cache data structures to provide
    efficient memory management across multiple cache shards.
    """

    def __init__(
        self,
        max_entries: int = 100000,
        max_memory_mb: int = 100,
        paranoia_mode: bool = False,
        enable_weak_refs: bool = False,
    ):
        """
        Initialize the cache memory manager.

        Args:
            max_entries: Maximum number of entries allowed in cache
            max_memory_mb: Maximum memory usage in MB
            paranoia_mode: Enable paranoid operational mode with lower bounds
        """
        self.max_entries = max_entries
        self.max_memory_mb = max_memory_mb
        self.paranoia_mode = paranoia_mode

        # In paranoia mode, lower the bounds significantly
        if self.paranoia_mode:
            self.max_entries = min(self.max_entries, 10000)  # Max 10K entries
            self.max_memory_mb = min(self.max_memory_mb, 10)  # Max 10MB

    def check_memory_bounds(
        self, shards: list[dict[str, CacheEntry]], current_size: int
    ) -> bool:
        """
        Check if cache size and memory usage are within safe bounds.

        Args:
            shards: List of cache shards to analyze
            current_size: Current number of entries in cache

        Returns:
            True if within bounds, False if too large or memory usage exceeded
        """
        # Check item count bounds first
        if not self._check_item_count_bounds(current_size):
            return False

        # Check memory usage bounds
        return self._check_memory_usage_bounds(shards, current_size)

    def _check_item_count_bounds(self, current_size: int) -> bool:
        """Check if item count is within safe bounds."""
        max_safe_size = self.max_entries

        if current_size > max_safe_size:
            logger.warning(
                f"Cache size {current_size} exceeds safe bounds {max_safe_size}",
                extra={
                    "correlation_id": runtime_metrics.create_correlation_id(
                        {
                            "component": "cache_memory_manager",
                            "operation": "bounds_check",
                            "current_size": current_size,
                            "max_safe_size": max_safe_size,
                        }
                    )
                },
            )
            return False
        return True

    def _check_memory_usage_bounds(
        self, shards: list[dict[str, CacheEntry]], current_size: int
    ) -> bool:
        """
        Check if memory usage is within safe bounds using sampling.

        Args:
            shards: List of cache shards to sample from
            current_size: Current number of entries in cache

        Returns:
            True if within bounds, False if memory usage exceeded
        """
        try:
            estimated_memory_mb = 0

            # Calculate more accurate memory usage by sampling some entries
            sample_size = min(100, current_size)  # Sample up to 100 entries
            sample_count = 0
            sample_memory = 0

            for shard in shards:
                for key, entry in shard.items():
                    if sample_count >= sample_size:
                        break
                    # Estimate memory for key and value
                    sample_memory += sys.getsizeof(key)
                    sample_memory += sys.getsizeof(entry.data)
                    sample_memory += sys.getsizeof(entry.timestamp)
                    sample_memory += sys.getsizeof(entry.ttl)
                    sample_count += 1
                if sample_count >= sample_size:
                    break

            # Extrapolate to full cache size
            if sample_count > 0:
                avg_memory_per_item = sample_memory / sample_count
                estimated_memory_mb = (avg_memory_per_item * current_size) / (
                    1024 * 1024
                )
            else:
                # Fallback to rough calculation if no items sampled
                estimated_memory_mb = (
                    current_size * 0.5
                )  # ~500KB per 1000 entries

            # Check if we're approaching the memory limit (80% threshold)
            memory_threshold = self.max_memory_mb * 0.8
            if estimated_memory_mb > memory_threshold:
                # Trigger graceful degradation measures when approaching the limit
                logger.warning(
                    f"Cache memory usage {estimated_memory_mb:.1f}MB approaching limit of {self.max_memory_mb}MB",
                    extra={
                        "correlation_id": runtime_metrics.create_correlation_id(
                            {
                                "component": "cache_memory_manager",
                                "operation": "memory_bounds_approaching",
                                "estimated_mb": estimated_memory_mb,
                                "current_size": current_size,
                                "sample_count": sample_count,
                                "avg_memory_per_item": (
                                    avg_memory_per_item
                                    if sample_count > 0
                                    else 0
                                ),
                                "max_memory_mb": self.max_memory_mb,
                                "threshold_reached": "80%",
                            }
                        )
                    },
                )

                # Implement auto-tuning for cache parameters to reduce memory usage
                if estimated_memory_mb > self.max_memory_mb:
                    logger.warning(
                        f"Estimated cache memory usage {estimated_memory_mb:.1f}MB exceeds {self.max_memory_mb}MB limit",
                        extra={
                            "correlation_id": runtime_metrics.create_correlation_id(
                                {
                                    "component": "cache_memory_manager",
                                    "operation": "memory_bounds_exceeded",
                                    "estimated_mb": estimated_memory_mb,
                                    "current_size": current_size,
                                    "sample_count": sample_count,
                                    "avg_memory_per_item": (
                                        avg_memory_per_item
                                        if sample_count > 0
                                        else 0
                                    ),
                                    "max_memory_mb": self.max_memory_mb,
                                }
                            )
                        },
                    )
                    return False

        except Exception as e:
            # If memory estimation fails, log and continue with basic size check
            logger.warning(
                f"Failed to estimate memory usage: {e}, proceeding with basic size check",
                extra={
                    "correlation_id": runtime_metrics.create_correlation_id(
                        {
                            "component": "cache_memory_manager",
                            "operation": "memory_bounds_check_error",
                            "error": str(e),
                        }
                    )
                },
            )
            # If we can't estimate memory, just check the size limit
            max_safe_size = self.max_entries
            if current_size > max_safe_size:
                return False

        return True

    def evict_to_fit(
        self,
        shards: list[dict[str, CacheEntry]],
        shard_locks: list[Any],
        required_bytes: int,
        exclude_key: str | None = None,
    ) -> int:
        """
        Evict entries to make room for new data requiring specified bytes.

        Args:
            shards: List of cache shards
            shard_locks: List of locks for each shard
            required_bytes: Number of bytes needed
            exclude_key: Key to exclude from eviction (newly added key)

        Returns:
            Number of bytes freed by eviction
        """
        import asyncio

        correlation_id = runtime_metrics.create_correlation_id(
            {
                "component": "cache_memory_manager",
                "operation": "evict_to_fit",
                "required_bytes": required_bytes,
                "exclude_key": exclude_key,
            }
        )

        try:
            bytes_freed = 0
            eviction_count = 0
            max_evictions = len(shards) * 2  # Prevent infinite loop

            # Continue evicting until we have enough space or hit max evictions
            while eviction_count < max_evictions:
                # Check if we have enough space now
                current_size = sum(len(shard) for shard in shards)
                if self._check_memory_usage_bounds(shards, current_size):
                    break

                # Find and evict LRU entry from any shard
                lru_key = None
                lru_shard_idx = None

                # First, try to find LRU key in current shard if we have context
                if exclude_key:
                    # This is a simplified approach - in practice, you'd need to know
                    # which shard contains the exclude_key
                    for i, shard in enumerate(shards):
                        if exclude_key in shard:
                            lru_key = self._get_lru_key(shard, exclude_key)
                            lru_shard_idx = i
                            break

                # If no LRU found in current shard or no exclude_key, search all shards
                if lru_key is None:
                    for i, shard in enumerate(shards):
                        candidate_key = self._get_lru_key(shard, exclude_key)
                        if candidate_key:
                            lru_key = candidate_key
                            lru_shard_idx = i
                            break

                if lru_key and lru_shard_idx is not None:
                    # Evict the LRU entry
                    shard = shards[lru_shard_idx]
                    lock = shard_locks[lru_shard_idx]

                    # Use asyncio since this is called from async context
                    async def do_eviction():
                        nonlocal bytes_freed
                        async with lock:
                            if lru_key in shard:
                                entry = shard[lru_key]
                                # Estimate bytes freed (rough approximation)
                                bytes_freed += sys.getsizeof(lru_key)
                                bytes_freed += sys.getsizeof(entry.data)
                                del shard[lru_key]
                                runtime_metrics.cache_evictions.increment()
                                return True
                        return False

                    # Run the eviction
                    evicted = asyncio.run(do_eviction())
                    if evicted:
                        eviction_count += 1
                        log_with_correlation(
                            logging.DEBUG,
                            f"LRU eviction freed key: {lru_key}",
                            correlation_id,
                        )
                    else:
                        break  # No more entries to evict
                else:
                    break  # No more LRU entries found

            log_with_correlation(
                logging.DEBUG,
                f"Eviction completed: freed {bytes_freed} bytes via {eviction_count} evictions",
                correlation_id,
            )

            return bytes_freed

        except Exception as e:
            log_with_correlation(
                logging.ERROR,
                f"Error during eviction: {e}",
                correlation_id,
            )
            return 0
        finally:
            runtime_metrics.close_correlation_id(correlation_id)

    def _get_lru_key(
        self, shard: dict[str, CacheEntry], exclude_key: str | None = None
    ) -> str | None:
        """
        Get the least recently used key in a shard, excluding specified key.

        Args:
            shard: Cache shard to search
            exclude_key: Key to exclude from consideration

        Returns:
            LRU key or None if shard is empty or only contains exclude_key
        """
        if not shard:
            return None

        # Find the entry with the oldest timestamp
        lru_key = None
        lru_timestamp = float("inf")

        for key, entry in shard.items():
            if exclude_key and key == exclude_key:
                continue

            if entry.timestamp < lru_timestamp:
                lru_timestamp = entry.timestamp
                lru_key = key

        return lru_key

    def estimate_cache_memory_usage(
        self, shards: list[dict[str, CacheEntry]]
    ) -> float:
        """
        Estimate current memory usage of cache in MB.

        Args:
            shards: List of cache shards to analyze

        Returns:
            Estimated memory usage in MB
        """
        try:
            total_memory = 0
            total_entries = 0

            for shard in shards:
                for key, entry in shard.items():
                    total_memory += sys.getsizeof(key)
                    total_memory += sys.getsizeof(entry.data)
                    total_memory += sys.getsizeof(entry.timestamp)
                    total_memory += sys.getsizeof(entry.ttl)
                    total_entries += 1

            if total_entries == 0:
                return 0.0

            # Convert to MB
            return total_memory / (1024 * 1024)

        except Exception as e:
            logger.warning(f"Failed to estimate cache memory usage: {e}")
            return 0.0

    def get_memory_info(
        self, shards: list[dict[str, CacheEntry]]
    ) -> dict[str, Any]:
        """
        Get comprehensive memory information for the cache.

        Args:
            shards: List of cache shards to analyze

        Returns:
            Dictionary with memory usage information
        """
        current_size = sum(len(shard) for shard in shards)
        estimated_memory_mb = self.estimate_cache_memory_usage(shards)

        return {
            "current_size": current_size,
            "estimated_memory_mb": estimated_memory_mb,
            "max_entries": self.max_entries,
            "max_memory_mb": self.max_memory_mb,
            "paranoia_mode": self.paranoia_mode,
            "within_bounds": self.check_memory_bounds(shards, current_size),
            "memory_utilization_percent": (
                (estimated_memory_mb / self.max_memory_mb * 100)
                if self.max_memory_mb > 0
                else 0
            ),
        }


# Import here to avoid circular imports
try:
    from resync_new.core.monitoring.metrics import log_with_correlation
except ImportError:
    # Fallback if metrics module not available
    def log_with_correlation(level, message, correlation_id):
        logger.log(level, message)
