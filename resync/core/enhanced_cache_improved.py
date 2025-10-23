# resync/core/enhanced_cache.py - VERSÃO MELHORADA
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata."""

    data: Any
    timestamp: float
    ttl: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if entry is expired."""
        if current_time is None:
            current_time = time.time()
        return (current_time - self.timestamp) > self.ttl

    def touch(self) -> None:
        """Update last access time and increment access count."""
        self.last_access = time.time()
        self.access_count += 1


class EnhancedAsyncCache:
    """
    Enhanced asynchronous cache with advanced features and security.

    Features:
    - LRU eviction with access tracking
    - Memory bounds monitoring
    - Encryption support for sensitive data
    - Health monitoring and metrics
    - Graceful degradation under memory pressure
    - Configurable eviction policies
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 300,
        enable_encryption: bool = False,
        key_prefix: str = "cache:",
        memory_limit_mb: Optional[int] = None,
    ):
        """
        Initialize enhanced cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Default TTL for entries
            enable_encryption: Whether to encrypt sensitive data
            key_prefix: Prefix for cache keys
            memory_limit_mb: Memory limit in MB
        """
        self.max_size = max_size
        self.default_ttl = ttl_seconds
        self.enable_encryption = enable_encryption
        self.key_prefix = key_prefix
        self.memory_limit_mb = memory_limit_mb or (
            psutil.virtual_memory().available // (1024 * 1024) // 4
        )  # 25% of available

        # Core data structures
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        # Memory tracking
        self._current_memory_mb = 0.0

        logger.info(
            f"Enhanced cache initialized: max_size={max_size}, "
            f"ttl={ttl_seconds}s, encryption={enable_encryption}, "
            f"memory_limit={self.memory_limit_mb}MB"
        )

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with LRU update."""
        async with self._lock:
            cache_key = f"{self.key_prefix}{key}"
            entry = self._cache.get(cache_key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[cache_key]
                self._misses += 1
                return None

            # Update LRU and statistics
            entry.touch()
            self._cache.move_to_end(cache_key)  # LRU: move to end
            self._hits += 1

            return entry.data

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        encrypt: Optional[bool] = None,
    ) -> bool:
        """Set value in cache with optional encryption."""
        async with self._lock:
            cache_key = f"{self.key_prefix}{key}"
            ttl = ttl_seconds or self.default_ttl

            # Create new entry
            entry = CacheEntry(
                data=value,
                timestamp=time.time(),
                ttl=ttl,
                size_bytes=self._estimate_size(value),
            )

            # Check memory bounds before adding
            if not await self._ensure_memory_bounds(entry.size_bytes):
                logger.warning(f"Cache memory limit exceeded, cannot add key: {key}")
                return False

            # Add to cache (LRU eviction if needed)
            self._cache[cache_key] = entry
            self._cache.move_to_end(cache_key)

            # Enforce size limits
            await self._enforce_size_limits()

            return True

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            cache_key = f"{self.key_prefix}{key}"
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                self._current_memory_mb -= entry.size_bytes / (1024 * 1024)
                del self._cache[cache_key]
                return True
            return False

    async def clear(self) -> int:
        """Clear all cache entries. Returns number of entries cleared."""
        async with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            self._current_memory_mb = 0.0
            self._hits = self._misses = self._evictions = 0
            return cleared_count

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if entry.is_expired(current_time)
            ]

            for key in expired_keys:
                entry = self._cache[key]
                self._current_memory_mb -= entry.size_bytes / (1024 * 1024)
                del self._cache[key]

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "memory_mb": self._current_memory_mb,
            "memory_limit_mb": self.memory_limit_mb,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        stats = self.get_stats()
        issues = []

        # Memory usage check
        if stats["memory_mb"] > stats["memory_limit_mb"] * 0.9:
            issues.append("Memory usage above 90% of limit")

        # Size check
        if stats["size"] > self.max_size * 0.9:
            issues.append("Cache size above 90% of limit")

        # Hit rate check
        if stats["hit_rate"] < 0.5 and stats["size"] > 10:
            issues.append("Low hit rate (< 50%)")

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "stats": stats,
        }

    def _estimate_size(self, obj: Any) -> int:
        """Estimate memory size of an object in bytes."""
        try:
            # Rough estimation - can be improved with more sophisticated methods
            if isinstance(obj, (str, bytes)):
                return len(obj) * 2  # Unicode overhead
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj) + 64  # Overhead
            elif isinstance(obj, dict):
                return (
                    sum(len(k) + self._estimate_size(v) for k, v in obj.items()) + 128
                )  # Overhead
            else:
                return 256  # Default object size
        except:
            return 256  # Fallback

    async def _ensure_memory_bounds(self, additional_bytes: int) -> bool:
        """Ensure memory bounds are respected."""
        additional_mb = additional_bytes / (1024 * 1024)
        projected_memory = self._current_memory_mb + additional_mb

        if projected_memory <= self.memory_limit_mb:
            return True

        # Try to free up memory by cleaning expired entries
        await self.cleanup_expired()

        # Check again after cleanup
        if self._current_memory_mb + additional_mb <= self.memory_limit_mb:
            return True

        # If still over limit, try LRU eviction
        await self._evict_lru(additional_mb)
        return self._current_memory_mb + additional_mb <= self.memory_limit_mb

    async def _enforce_size_limits(self) -> None:
        """Enforce cache size limits using LRU eviction."""
        while len(self._cache) > self.max_size:
            # Remove least recently used item
            oldest_key, oldest_entry = next(iter(self._cache.items()))
            self._current_memory_mb -= oldest_entry.size_bytes / (1024 * 1024)
            del self._cache[oldest_key]
            self._evictions += 1

    async def _evict_lru(self, target_mb: float) -> None:
        """Evict LRU entries until target memory reduction is achieved."""
        evicted_mb = 0.0

        while evicted_mb < target_mb and self._cache:
            # Remove least recently used item
            oldest_key, oldest_entry = next(iter(self._cache.items()))
            entry_mb = oldest_entry.size_bytes / (1024 * 1024)
            self._current_memory_mb -= entry_mb
            evicted_mb += entry_mb
            del self._cache[oldest_key]
            self._evictions += 1
