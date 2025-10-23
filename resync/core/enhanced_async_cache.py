from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single entry in the cache with timestamp and TTL."""

    data: Any
    timestamp: float
    ttl: float


class ConsistentHash:
    """
    Implements consistent hashing for better key distribution and shard stability.

    This implementation uses a ring-based approach with virtual nodes to ensure
    even distribution of keys across shards.
    """

    def __init__(self, num_shards: int, replicas: int = 100):
        """
        Initialize the consistent hash ring.

        Args:
            num_shards: Number of shards to distribute keys across
            replicas: Number of virtual nodes per shard for better distribution
        """
        self.num_shards = num_shards
        self.replicas = replicas
        self.ring: Dict[int, int] = {}
        self._build_ring()

    def _build_ring(self) -> None:
        """Build the hash ring with virtual nodes."""
        for shard_id in range(self.num_shards):
            for replica in range(self.replicas):
                key = f"{shard_id}:{replica}"
                hash_key = self._hash(key)
                self.ring[hash_key] = shard_id

        # Sort the keys for binary search
        self._sorted_keys = sorted(self.ring.keys())

    def _hash(self, key: str) -> int:
        """Create a hash for a key."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def get_shard(self, key: str) -> int:
        """
        Get the shard ID for a given key.

        Args:
            key: The key to hash

        Returns:
            The shard ID (0 to num_shards-1)
        """
        if not self._sorted_keys:
            return 0

        hash_key = self._hash(key)

        # Binary search to find the next highest key
        pos = self._binary_search(hash_key)

        # If we're at the end, wrap around to the first node
        if pos == len(self._sorted_keys):
            pos = 0

        # Return the shard ID for this position in the ring
        return self.ring[self._sorted_keys[pos]]

    def _binary_search(self, hash_key: int) -> int:
        """Find the position of the next highest key in the sorted keys."""
        lo, hi = 0, len(self._sorted_keys) - 1

        # If the hash is greater than all keys, return the position after the last key
        if hash_key > self._sorted_keys[hi]:
            return len(self._sorted_keys)

        # Binary search
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._sorted_keys[mid] < hash_key:
                lo = mid + 1
            else:
                hi = mid - 1

        return lo


class KeyLock:
    """
    Implements fine-grained locking at the key level.

    This allows multiple operations on different keys within the same shard
    to proceed concurrently, reducing lock contention.
    """

    def __init__(self, max_locks: int = 1024):
        """
        Initialize the key lock manager.

        Args:
            max_locks: Maximum number of concurrent locks to maintain
        """
        self.max_locks = max_locks
        self.locks: Dict[str, asyncio.Lock] = {}
        self.lock_access_times: Dict[str, float] = {}
        self.global_lock = asyncio.Lock()

    async def acquire(self, key: str) -> asyncio.Lock:
        """
        Get a lock for a specific key, creating it if necessary.

        Args:
            key: The key to lock

        Returns:
            An asyncio.Lock object for the key
        """
        async with self.global_lock:
            # Clean up old locks if we've reached the limit
            if len(self.locks) >= self.max_locks:
                await self._cleanup_old_locks()

            # Create a new lock if needed
            if key not in self.locks:
                self.locks[key] = asyncio.Lock()

            # Update access time
            self.lock_access_times[key] = time.time()

            return self.locks[key]

    async def _cleanup_old_locks(self) -> None:
        """Remove the least recently used locks to stay under max_locks."""
        # Create a copy of locks dict to avoid modification during iteration
        locks_copy = self.locks.copy()
        access_times_copy = self.lock_access_times.copy()

        # Only clean up locks that aren't currently held
        available_locks = [
            k
            for k, lock in locks_copy.items()
            if not lock.locked() and k in access_times_copy
        ]

        if not available_locks:
            return  # All locks are in use, can't clean up

        # Sort by access time and remove oldest
        oldest_keys = sorted(available_locks, key=lambda k: access_times_copy.get(k, 0))

        # Remove the oldest third of unused locks, but with safety check
        to_remove = oldest_keys[: max(1, len(oldest_keys) // 3)]

        # Double-check locks are still available before deletion
        for key in to_remove:
            if key in self.locks and not self.locks[key].locked():
                del self.locks[key]
                del self.lock_access_times[key]
                logger.debug("cleaned_up_lock", key=key)
            else:
                logger.debug("skipped_cleanup_for_lock_still_in_use", key=key)


class ShardLockManager:
    """
    Simplified lock manager with optimized locking strategy.

    Uses a single KeyLock manager for all shards to reduce overhead
    and simplify the locking architecture.
    """

    def __init__(self, num_shards: int):
        """
        Initialize the simplified shard lock manager.

        Args:
            num_shards: Number of shards (for compatibility)
        """
        # Use a single KeyLock manager for all keys across all shards
        # This simplifies locking and reduces memory usage
        self.key_lock_manager = KeyLock(
            max_locks=2048
        )  # Increased for better performance
        self.num_shards = num_shards  # Keep for compatibility

    async def acquire_shard_lock(self, shard_id: int) -> asyncio.Lock:
        """
        Get a lock for an entire shard.

        Args:
            shard_id: The shard ID

        Returns:
            A shard-level lock (uses key-based locking for simplicity)
        """
        # For shard locks, use a key-based approach
        lock = await self.key_lock_manager.acquire(f"shard_{shard_id}")
        return lock


class TWS_OptimizedAsyncCache:
    """
    TWS-Optimized Async Cache implementation with sharding and TTL support.

    This cache is specifically designed to handle TWS (Tivoli Workload Scheduler)
    data patterns efficiently with:
    - Sharded architecture for concurrent access
    - TTL-based expiration
    - Background cleanup
    - Consistent hashing for key distribution
    - Fine-grained locking
    """

    def __init__(
        self,
        ttl_seconds: int = 300,
        cleanup_interval: int = 30,
        num_shards: int = 8,
        max_workers: int = 4,
    ):
        """
        Initialize the TWS-optimized async cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
            cleanup_interval: Interval between cleanup runs in seconds
            num_shards: Number of shards for concurrent access
            max_workers: Maximum number of worker threads for cleanup
        """
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self.num_shards = num_shards
        self.max_workers = max_workers

        # Initialize sharded data structures
        self.shards: List[Dict[str, CacheEntry]] = [{} for _ in range(num_shards)]
        self.consistent_hash = ConsistentHash(num_shards)
        self.lock_manager = ShardLockManager(num_shards)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # Background task management
        self.cleanup_task: Optional[asyncio.Task[None]] = None
        self.running = False

    def _get_shard(self, key: str) -> int:
        """Get the shard ID for a given key."""
        return self.consistent_hash.get_shard(key)

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        if not key:
            return None

        shard_id = self._get_shard(key)
        shard = self.shards[shard_id]

        # Acquire key-level lock
        lock = await self.lock_manager.acquire_shard_lock(shard_id)
        async with lock:
            if key in shard:
                entry = shard[key]
                if time.time() - entry.timestamp <= entry.ttl:
                    return entry.data
                else:
                    # Entry expired, remove it
                    del shard[key]
            return None

    async def set(
        self, key: str, value: Any, ttl_seconds: Optional[int] = None
    ) -> None:
        """Set a value in the cache."""
        if not key:
            return

        shard_id = self._get_shard(key)
        shard = self.shards[shard_id]
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds

        # Acquire key-level lock
        lock = await self.lock_manager.acquire_shard_lock(shard_id)
        async with lock:
            shard[key] = CacheEntry(
                data=value,
                timestamp=time.time(),
                ttl=ttl,
            )

    async def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        if not key:
            return False

        shard_id = self._get_shard(key)
        shard = self.shards[shard_id]

        # Acquire key-level lock
        lock = await self.lock_manager.acquire_shard_lock(shard_id)
        async with lock:
            if key in shard:
                del shard[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        for shard in self.shards:
            shard.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired entries from the cache."""
        cleaned = 0
        current_time = time.time()

        for shard in self.shards:
            expired_keys = [
                key
                for key, entry in shard.items()
                if current_time - entry.timestamp > entry.ttl
            ]
            for key in expired_keys:
                del shard[key]
                cleaned += 1

        return cleaned

    async def start(self) -> None:
        """Start the background cleanup task."""
        if not self.running:
            self.running = True
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        if self.running:
            self.running = False
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass

    async def _cleanup_loop(self) -> None:
        """Background task to periodically clean up expired entries."""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                cleaned = await self.cleanup_expired()
                if cleaned > 0:
                    logger.debug("cleaned_up_expired_cache_entries", count=cleaned)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error_in_cache_cleanup", error=str(e))

    async def size(self) -> int:
        """Get the total number of entries in the cache."""
        return sum(len(shard) for shard in self.shards)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = await self.size()
        per_shard = [len(shard) for shard in self.shards]
        return {
            "total_entries": total_size,
            "shards": self.num_shards,
            "per_shard": per_shard,
            "ttl_seconds": self.ttl_seconds,
            "cleanup_interval": self.cleanup_interval,
        }

    async def __aenter__(self) -> "TWS_OptimizedAsyncCache":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[Any],
    ) -> None:
        """Async context manager exit."""
        await self.stop()
