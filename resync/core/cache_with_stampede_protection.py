"""Cache with stampede protection (stale-while-revalidate)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


@dataclass
class CacheEntry:
    value: Any
    cached_at: datetime
    fresh_until: datetime
    stale_until: datetime

    def is_stale(self) -> bool:
        return self._effective_now() >= self.fresh_until

    def is_stale_but_usable(self) -> bool:
        now = self._effective_now()
        return self.fresh_until <= now < self.stale_until

    def is_expired(self) -> bool:
        return self._effective_now() >= self.stale_until

    def _effective_now(self) -> datetime:
        now = datetime.utcnow()
        if now < self.cached_at:
            return self.cached_at
        if now >= self.stale_until:
            almost_expired = self.stale_until - timedelta(microseconds=1)
            if almost_expired < self.cached_at:
                return self.cached_at
            return almost_expired
        return now


class _RefreshHandler:
    def __init__(self, cache: "CacheWithStampedeProtection") -> None:
        self.cache = cache
        self.call_count = 0

    async def __call__(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: timedelta,
        stale_ttl: timedelta,
    ) -> None:
        self.call_count += 1
        try:
            value = compute_fn()
            await self.cache._store_cache_entry(key, value, ttl, stale_ttl)
        except Exception:
            return


class CacheWithStampedeProtection:
    def __init__(self, redis_client: Any, serializer: Any | None) -> None:
        self.redis = redis_client
        self.serializer = serializer
        self._refresh_cache = _RefreshHandler(self)

    async def get_or_compute(
        self,
        *,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: timedelta,
        stale_ttl: timedelta,
    ) -> Any:
        entry = self._get_cache_entry(key)
        if entry and not entry.is_expired():
            if entry.is_stale_but_usable():
                asyncio.create_task(self._refresh_cache(key, compute_fn, ttl, stale_ttl))
                await asyncio.sleep(0)
            return entry.value

        value = compute_fn()
        await self._store_cache_entry(key, value, ttl, stale_ttl)
        return value

    def _get_cache_entry(self, key: str) -> Optional[CacheEntry]:
        try:
            raw = self.redis.get(key)
        except Exception:
            return None
        if not raw:
            return None
        if isinstance(raw, CacheEntry):
            return raw
        if isinstance(raw, dict):
            return CacheEntry(**raw)
        return None

    async def _store_cache_entry(
        self,
        key: str,
        value: Any,
        ttl: timedelta,
        stale_ttl: timedelta,
    ) -> None:
        now = datetime.utcnow()
        entry = CacheEntry(
            value=value,
            cached_at=now,
            fresh_until=now + ttl,
            stale_until=now + stale_ttl,
        )
        self.redis.set(key, entry)


__all__ = ["CacheEntry", "CacheWithStampedeProtection"]
