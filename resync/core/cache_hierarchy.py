"""Two-level cache hierarchy implementation for tests."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


class L1Cache:
    """In-memory L1 cache with simple LRU behaviour."""

    def __init__(self, max_size: int = 128) -> None:
        self.max_size = max_size
        self._data: "OrderedDict[str, Any]" = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any:
        async with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._data.pop(key, None) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()

    def size(self) -> int:
        return len(self._data)


class _L2Cache:
    def __init__(self, ttl_seconds: float, cleanup_interval: float, num_shards: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self.num_shards = num_shards
        self._data: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        if cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup()
        except asyncio.CancelledError:  # pragma: no cover
            return

    async def cleanup(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [key for key, (_, expiry) in self._data.items() if expiry < now]
            for key in expired:
                self._data.pop(key, None)

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def get(self, key: str) -> Any:
        async with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            value, expiry = entry
            if expiry < time.time():
                self._data.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = (value, time.time() + self.ttl_seconds)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    def size(self) -> int:
        return len(self._data)


@dataclass
class CacheMetrics:
    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0
    total_gets: int = 0
    total_sets: int = 0

    @property
    def l1_hit_ratio(self) -> float:
        total = self.l1_hits + self.l1_misses
        return self.l1_hits / total if total else 0.0

    @property
    def l2_hit_ratio(self) -> float:
        total = self.l2_hits + self.l2_misses
        return self.l2_hits / total if total else 0.0

    @property
    def overall_hit_ratio(self) -> float:
        return (self.l1_hits + self.l2_hits) / self.total_gets if self.total_gets else 0.0


class CacheHierarchy:
    """Simple L1 + L2 cache hierarchy."""

    def __init__(
        self,
        *,
        l1_max_size: int = 256,
        l2_ttl_seconds: float = 60.0,
        l2_cleanup_interval: float = 30.0,
        num_shards: int = 8,
    ) -> None:
        self.l1 = L1Cache(max_size=l1_max_size)
        self.l2 = _L2Cache(
            ttl_seconds=l2_ttl_seconds,
            cleanup_interval=l2_cleanup_interval,
            num_shards=num_shards,
        )
        self.metrics = CacheMetrics()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        await self.l2.close()

    async def get(self, key: str) -> Any:
        self.metrics.total_gets += 1
        value = await self.l1.get(key)
        if value is not None:
            self.metrics.l1_hits += 1
            return value
        self.metrics.l1_misses += 1
        value = await self.l2.get(key)
        if value is not None:
            self.metrics.l2_hits += 1
            await self.l1.set(key, value)
            return value
        self.metrics.l2_misses += 1
        return None

    async def set(self, key: str, value: Any, *, ttl_seconds: Optional[float] = None) -> None:
        self.metrics.total_sets += 1
        await self.l1.set(key, value)
        await self.l2.set(key, value)

    async def set_from_source(self, key: str, value: Any, *, ttl_seconds: Optional[float] = None) -> None:
        await self.set(key, value, ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> bool:
        removed_l1 = await self.l1.delete(key)
        await self.l2.delete(key)
        return removed_l1

    async def clear(self) -> None:
        await self.l1.clear()
        await self.l2.close()
        self.l2 = _L2Cache(
            ttl_seconds=self.l2.ttl_seconds,
            cleanup_interval=self.l2.cleanup_interval,
            num_shards=self.l2.num_shards,
        )

    def size(self) -> Tuple[int, int]:
        l1_size = self.l1.size()
        l2_size = self.l2.size()
        return l1_size, l2_size


_cache_singleton: CacheHierarchy | None = None


def get_cache_hierarchy() -> CacheHierarchy:
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = CacheHierarchy()
    return _cache_singleton


__all__ = ["CacheHierarchy", "CacheMetrics", "L1Cache", "get_cache_hierarchy"]
