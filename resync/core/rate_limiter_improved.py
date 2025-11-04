"""Enhanced rate limiting algorithms used by integration tests."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Dict


class TokenBucketRateLimiter:
    """Token bucket rate limiter with async helpers."""

    def __init__(self, rate: float, capacity: float, name: str) -> None:
        self.rate = float(rate)
        self.capacity = float(capacity)
        self.name = name

        self.tokens = float(capacity)
        self._last_refill = time.monotonic()

        self.requests_allowed = 0
        self.requests_denied = 0
        self.tokens_consumed = 0.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self.tokens = min(
            self.capacity, self.tokens + elapsed * self.rate
        )

    async def acquire(self, amount: float = 1.0) -> bool:
        """Attempt to consume tokens; return True on success."""
        self._refill()
        if amount <= self.tokens:
            self.tokens -= amount
            self.requests_allowed += 1
            self.tokens_consumed += amount
            return True
        self.requests_denied += 1
        return False

    async def wait_and_acquire(self, amount: float = 1.0) -> None:
        """Block until the requested amount can be consumed."""
        while not await self.acquire(amount):
            deficit = max(0.0, amount - self.tokens)
            sleep_time = deficit / self.rate if self.rate > 0 else 0.1
            await asyncio.sleep(max(0.01, sleep_time))

    def get_stats(self) -> Dict[str, Any]:
        total = self.requests_allowed + self.requests_denied
        success_rate = (
            self.requests_allowed / total if total else 0.0
        )
        return {
            "algorithm": "token_bucket",
            "name": self.name,
            "tokens": self.tokens,
            "rate": self.rate,
            "capacity": self.capacity,
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "success_rate": success_rate,
            "tokens_consumed": self.tokens_consumed,
        }


class LeakyBucketRateLimiter:
    """Leaky bucket limiter backed by an async draining task."""

    def __init__(self, rate: float, capacity: int, name: str) -> None:
        self.rate = float(rate)
        self.capacity = int(capacity)
        self.name = name

        self.queue: deque[float] = deque()
        self.requests_allowed = 0
        self.requests_denied = 0
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._leak_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def _leak_loop(self) -> None:
        interval = 1.0 / self.rate if self.rate > 0 else 0.5
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                if self.queue:
                    self.queue.popleft()

    async def acquire(self) -> bool:
        async with self._lock:
            if len(self.queue) < self.capacity:
                self.queue.append(time.monotonic())
                self.requests_allowed += 1
                return True
            self.requests_denied += 1
            return False

    async def wait_and_acquire(self) -> None:
        while not await self.acquire():
            await asyncio.sleep(1.0 / self.rate if self.rate else 0.5)

    def get_stats(self) -> Dict[str, Any]:
        running = self._task is not None and not self._task.done()
        return {
            "algorithm": "leaky_bucket",
            "name": self.name,
            "rate": self.rate,
            "capacity": self.capacity,
            "current_queue_size": len(self.queue),
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "running": running,
        }


class SlidingWindowRateLimiter:
    """Sliding window limiter using timestamps to enforce limits."""

    def __init__(
        self, requests_per_window: int, window_seconds: float, name: str
    ) -> None:
        self.requests_per_window = int(requests_per_window)
        self.window_seconds = float(window_seconds)
        self.name = name

        self.requests: deque[float] = deque()
        self.requests_allowed = 0
        self.requests_denied = 0

    def _prune(self, now: float) -> None:
        window_start = now - self.window_seconds
        while self.requests and self.requests[0] <= window_start:
            self.requests.popleft()

    async def acquire(self) -> bool:
        now = time.monotonic()
        self._prune(now)

        if len(self.requests) < self.requests_per_window:
            self.requests.append(now)
            self.requests_allowed += 1
            return True
        self.requests_denied += 1
        return False

    def get_stats(self) -> Dict[str, Any]:
        total = self.requests_allowed + self.requests_denied
        success_rate = (
            self.requests_allowed / total if total else 0.0
        )
        return {
            "algorithm": "sliding_window",
            "name": self.name,
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "success_rate": success_rate,
            "current_window_size": len(self.requests),
        }


class RateLimiterManager:
    """Factory and registry for rate limiters used in tests."""

    def __init__(self) -> None:
        self._limiters: dict[str, Any] = {}

    def _register(self, name: str, limiter: Any) -> Any:
        if name in self._limiters:
            raise ValueError(f"Rate limiter '{name}' already exists")
        self._limiters[name] = limiter
        return limiter

    def get_limiter(self, name: str) -> Any:
        try:
            return self._limiters[name]
        except KeyError as exc:
            raise KeyError(f"Rate limiter '{name}' not found") from exc

    async def remove_limiter(self, name: str) -> bool:
        limiter = self._limiters.pop(name, None)
        if limiter is None:
            return False
        if hasattr(limiter, "stop"):
            await limiter.stop()
        return True

    async def create_token_bucket(
        self, name: str, rate: float, capacity: float
    ) -> TokenBucketRateLimiter:
        limiter = TokenBucketRateLimiter(rate, capacity, name)
        return self._register(name, limiter)

    async def create_leaky_bucket(
        self, name: str, rate: float, capacity: int
    ) -> LeakyBucketRateLimiter:
        limiter = LeakyBucketRateLimiter(rate, capacity, name)
        await limiter.start()
        return self._register(name, limiter)

    async def create_sliding_window(
        self, name: str, requests_per_window: int, window_seconds: float
    ) -> SlidingWindowRateLimiter:
        limiter = SlidingWindowRateLimiter(
            requests_per_window, window_seconds, name
        )
        return self._register(name, limiter)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        return {name: limiter.get_stats() for name, limiter in self._limiters.items()}

    async def shutdown(self) -> None:
        for limiter in list(self._limiters.values()):
            if hasattr(limiter, "stop"):
                await limiter.stop()
        self._limiters.clear()


__all__ = [
    "TokenBucketRateLimiter",
    "LeakyBucketRateLimiter",
    "SlidingWindowRateLimiter",
    "RateLimiterManager",
]
