"""Compatibility layer providing migration managers for cache, TWS and rate limiting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Lightweight async cache
# ---------------------------------------------------------------------------
class _InMemoryAsyncCache:
    def __init__(self) -> None:
        self._storage: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            return self._storage.get(key)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._storage[key] = value

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._storage.pop(key, None) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._storage.clear()


class CacheMigrationManager:
    """Wrapper that coordinates migration between legacy and new caches."""

    def __init__(self) -> None:
        self.use_new_cache = False
        self.legacy_cache: _InMemoryAsyncCache | None = None
        self.new_cache: _InMemoryAsyncCache | None = None

    async def initialize(self) -> None:
        self.legacy_cache = _InMemoryAsyncCache()
        self.new_cache = _InMemoryAsyncCache()

    async def shutdown(self) -> None:
        if self.legacy_cache:
            await self.legacy_cache.clear()
        if self.new_cache:
            await self.new_cache.clear()

    async def get(self, key: str) -> Any | None:
        assert self.legacy_cache and self.new_cache
        try:
            if self.use_new_cache:
                value = await self.new_cache.get(key)
                if value is not None:
                    return value
            return await self.legacy_cache.get(key)
        except Exception:
            return await self.legacy_cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        assert self.legacy_cache and self.new_cache
        await self.legacy_cache.set(key, value)
        if self.use_new_cache:
            try:
                await self.new_cache.set(key, value)
            except Exception:
                # best-effort write; fallback to legacy already performed
                pass

    async def delete(self, key: str) -> bool:
        assert self.legacy_cache and self.new_cache
        deleted_legacy = await self.legacy_cache.delete(key)
        deleted_new = False
        try:
            deleted_new = await self.new_cache.delete(key)
        except Exception:
            pass
        return deleted_legacy or deleted_new

    async def clear(self) -> None:
        assert self.legacy_cache and self.new_cache
        await self.legacy_cache.clear()
        await self.new_cache.clear()


# ---------------------------------------------------------------------------
# TWS migration manager
# ---------------------------------------------------------------------------
class _TWSClientStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        self.connected = False
        return True


class TWSMigrationManager:
    """Handle gradual rollout of a new TWS client."""

    def __init__(self) -> None:
        self.use_new_client = False
        self.legacy_client: _TWSClientStub | None = None
        self.new_client: _TWSClientStub | None = None

    async def initialize(self) -> None:
        self.legacy_client = _TWSClientStub("legacy-tws-client")
        self.new_client = _TWSClientStub("new-tws-client")

    async def connect(self) -> bool:
        assert self.legacy_client and self.new_client
        client = self.new_client if self.use_new_client else self.legacy_client
        return await client.connect()

    async def shutdown(self) -> None:
        if self.legacy_client:
            await self.legacy_client.disconnect()
        if self.new_client:
            await self.new_client.disconnect()


# ---------------------------------------------------------------------------
# Rate limit migration manager
# ---------------------------------------------------------------------------
@dataclass
class _TokenBucket:
    capacity: int
    refill_rate_per_sec: float
    tokens: float = field(init=False)
    last_refill: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last_refill = datetime.utcnow()

    def acquire(self, amount: float = 1.0) -> bool:
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()
        self.last_refill = now
        self.tokens = min(
            self.capacity, self.tokens + elapsed * self.refill_rate_per_sec
        )

        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def stats(self) -> dict[str, float]:
        return {
            "capacity": float(self.capacity),
            "available_tokens": max(0.0, self.tokens),
            "refill_rate_per_sec": self.refill_rate_per_sec,
        }


class RateLimitMigrationManager:
    """Coordinate migration from legacy to new rate limiting implementation."""

    def __init__(self) -> None:
        self.use_new_limiter = False
        self.new_limiter: _TokenBucket | None = None

    async def initialize(self) -> None:
        self.new_limiter = _TokenBucket(capacity=10, refill_rate_per_sec=1.0)

    async def acquire(self, cost: float = 1.0) -> bool:
        if not self.use_new_limiter:
            return True
        assert self.new_limiter is not None
        return self.new_limiter.acquire(cost)

    def get_stats(self) -> dict[str, Any]:
        return {
            "migration_mode": "new" if self.use_new_limiter else "legacy",
            "new_limiter_stats": self.new_limiter.stats()
            if self.new_limiter
            else {},
        }

    async def shutdown(self) -> None:
        self.new_limiter = None


# ---------------------------------------------------------------------------
# Global lifecycle helpers
# ---------------------------------------------------------------------------
cache_migration_manager = CacheMigrationManager()
tws_migration_manager = TWSMigrationManager()
rate_limit_migration_manager = RateLimitMigrationManager()


async def initialize_migration_managers() -> None:
    await cache_migration_manager.initialize()
    await tws_migration_manager.initialize()
    await rate_limit_migration_manager.initialize()


async def shutdown_migration_managers() -> None:
    await cache_migration_manager.shutdown()
    await tws_migration_manager.shutdown()
    await rate_limit_migration_manager.shutdown()


__all__ = [
    "CacheMigrationManager",
    "TWSMigrationManager",
    "RateLimitMigrationManager",
    "cache_migration_manager",
    "tws_migration_manager",
    "rate_limit_migration_manager",
    "initialize_migration_managers",
    "shutdown_migration_managers",
]
