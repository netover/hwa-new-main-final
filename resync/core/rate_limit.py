"""
In-memory rate limiting utilities.

This module implements a simple token bucket rate limiter suitable for
protecting API endpoints against bursts of traffic.  It uses asyncio
locks to ensure thread safety when used in an async context.  For
distributed rate limiting consider implementing a Redis-backed bucket
using the same interface.
"""

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Any, Awaitable, Callable, Optional

from fastapi import HTTPException


class InMemoryBucket:
    """A simple token bucket for local rate limiting."""

    def __init__(self, rate: int, per: float) -> None:
        self.rate = rate
        self.per = per
        self.tokens: float = rate
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            elapsed = now - self.updated
            refill = elapsed * (self.rate / self.per)
            self.tokens = min(self.rate, self.tokens + refill)
            self.updated = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


def rate_limited(
    rate: int = 10,
    per: float = 1.0,
    bucket: Optional[InMemoryBucket] = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator to enforce a token bucket rate limit on async endpoints.

    Args:
        rate: Number of allowed requests per interval.
        per: Interval length in seconds.
        bucket: Optional shared bucket instance; if ``None`` a per-endpoint
            bucket is created.

    Returns:
        A decorator that wraps an async endpoint and raises HTTP 429 when
        the rate limit is exceeded.
    """
    shared_bucket = bucket or InMemoryBucket(rate, per)

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            allowed = await shared_bucket.allow()
            if not allowed:
                raise HTTPException(status_code=429, detail="Too Many Requests")
            return await fn(*args, **kwargs)

        return wrapper

    return decorator