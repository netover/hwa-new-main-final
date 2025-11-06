"""Async TTL cache used in tests for compatibility."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

LOGGER = logging.getLogger("resync.cache")


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class AsyncTTLCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = 60.0,
        cleanup_interval: float = 30.0,
        num_shards: int = 8,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self.num_shards = max(1, num_shards)

        self.shards: List[Dict[str, _CacheEntry]] = [dict() for _ in range(self.num_shards)]
        self.shard_locks: List[asyncio.Lock] = [asyncio.Lock() for _ in range(self.num_shards)]
        self._shard_id_to_index = {id(shard): idx for idx, shard in enumerate(self.shards)}

        self._contention_counts = [0 for _ in range(self.num_shards)]
        self._acquisition_times = [0.0 for _ in range(self.num_shards)]
        self._acquisition_samples = [0 for _ in range(self.num_shards)]

        self._cleanup_task: asyncio.Task | None = None
        if self.cleanup_interval and self.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    def _pick_shard_index(self, key: str) -> int:
        return hash(key) % self.num_shards

    def _get_shard(self, key: str) -> Tuple[Dict[str, _CacheEntry], asyncio.Lock]:
        idx = self._pick_shard_index(key)
        return self.shards[idx], self.shard_locks[idx]

    async def set(self, key: str, value: Any, *, ttl_seconds: float | None = None) -> None:
        idx = self._pick_shard_index(key)
        shard = self.shards[idx]
        lock = self.shard_locks[idx]
        start = time.perf_counter()
        locked = lock.locked()
        await lock.acquire()
        acquired = time.perf_counter()
        try:
            if locked:
                self._contention_counts[idx] += 1
                self._acquisition_times[idx] += acquired - start
                self._acquisition_samples[idx] += 1
            ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
            shard[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)
        finally:
            lock.release()

    async def get(self, key: str) -> Any:
        idx = self._pick_shard_index(key)
        shard = self.shards[idx]
        lock = self.shard_locks[idx]
        start = time.perf_counter()
        locked = lock.locked()
        await lock.acquire()
        acquired = time.perf_counter()
        try:
            if locked:
                self._contention_counts[idx] += 1
                self._acquisition_times[idx] += acquired - start
                self._acquisition_samples[idx] += 1
            entry = shard.get(key)
            if not entry:
                return None
            if entry.expires_at < time.time():
                shard.pop(key, None)
                return None
            return entry.value
        finally:
            lock.release()

    async def delete(self, key: str) -> None:
        shard, lock = self._get_shard(key)
        await lock.acquire()
        try:
            shard.pop(key, None)
        finally:
            lock.release()

    async def _periodic_cleanup(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired()
        except asyncio.CancelledError:  # pragma: no cover - expected on shutdown
            return

    async def cleanup_expired(self) -> None:
        now = time.time()
        for idx, shard in enumerate(self.shards):
            lock = self.shard_locks[idx]
            await lock.acquire()
            try:
                keys_to_delete = [k for k, entry in shard.items() if entry.expires_at < now]
                for key in keys_to_delete:
                    shard.pop(key, None)
            finally:
                lock.release()

    def get_hot_shards(self, threshold_percentile: float = 0.8) -> List[int]:
        counts = [len(shard) for shard in self.shards]
        if not counts:
            return []
        threshold_percentile = max(0.0, min(1.0, threshold_percentile))
        sorted_counts = sorted(counts)
        index = int((len(sorted_counts) - 1) * threshold_percentile)
        threshold = sorted_counts[index]
        return [idx for idx, count in enumerate(counts) if count >= threshold and count > 0]

    def get_detailed_metrics(self) -> Dict[str, Any]:
        sizes = [len(shard) for shard in self.shards]
        avg_times = []
        for idx in range(self.num_shards):
            samples = self._acquisition_samples[idx]
            if samples:
                avg_times.append(self._acquisition_times[idx] / samples)
            else:
                avg_times.append(0.0)
        return {
            "size_per_shard": sizes,
            "size": sum(sizes),
            "lock_contention": {
                "contention_counts": list(self._contention_counts),
                "avg_acquisition_times": avg_times,
            },
        }

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

    async def stop(self) -> None:
        await self.close()


__all__ = ["AsyncTTLCache"]
