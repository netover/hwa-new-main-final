"""
Simple rate limiter implementation for Resync API.

Uses in-memory storage for simplicity. For production, consider Redis-backed rate limiting.
"""

import asyncio
import time
from collections import defaultdict
from functools import wraps
from typing import Dict, Tuple

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.responses import JSONResponse

from resync.config.settings import settings
from resync.utils.simple_logger import get_logger


logger = get_logger(__name__)


class RateLimitConfig:
    """Default rate limit strings for various endpoint categories."""

    PUBLIC_ENDPOINTS = "100/minute"
    AUTHENTICATED_ENDPOINTS = "1000/minute"
    CRITICAL_ENDPOINTS = "50/minute"
    ERROR_HANDLER = "15/minute"
    WEBSOCKET = "30/minute"
    DASHBOARD = "10/minute"


_slowapi_limiter: Limiter | None = None


class SimpleRateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., IP address, user ID)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Remove old requests outside the window
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if req_time > window_start
            ]

            # Check if under limit
            if len(self._requests[key]) < limit:
                self._requests[key].append(now)
                remaining = limit - len(self._requests[key])
                return True, remaining

            # Rate limit exceeded
            return False, 0

    async def get_remaining_time(self, key: str, window_seconds: int = 60) -> int:
        """Get remaining time until rate limit resets."""
        if key not in self._requests:
            return 0

        oldest_request = min(self._requests[key])
        reset_time = oldest_request + window_seconds
        remaining = max(0, int(reset_time - time.time()))
        return remaining


# Global rate limiter instance
rate_limiter = SimpleRateLimiter()
limiter = rate_limiter  # Alias preserved for backwards compatibility


def _build_rate_limit_key(request: Request, key_prefix: str) -> str:
    """Generate a rate limit key based on the provided prefix."""
    if key_prefix == "ip":
        client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
        return f"ip:{client_ip}"
    if key_prefix == "user":
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
        return f"ip:{client_ip}"
    return f"{key_prefix}:default"


async def check_rate_limit(
    request: Request,
    limit: int,
    key_prefix: str = "ip"
) -> None:
    """
    Check rate limit for a request.

    Args:
        request: FastAPI request
        limit: Rate limit per minute
        key_prefix: Type of key to use ("ip", "user", etc.)

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Generate key based on type
    key = _build_rate_limit_key(request, key_prefix)

    allowed, remaining = await rate_limiter.check_rate_limit(key, limit)

    if not allowed:
        reset_time = await rate_limiter.get_remaining_time(key)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time} seconds.",
            headers={"Retry-After": str(reset_time)}
        )

    # Store rate limit info in request state for logging
    if not hasattr(request.state, "rate_limit"):
        request.state.rate_limit = {}
    request.state.rate_limit.update(
        {
            "limit": limit,
            "remaining": remaining,
            "reset_time": await rate_limiter.get_remaining_time(key),
        }
    )


# Convenience decorators
def public_rate_limit(func):
    """Decorator for public endpoints rate limiting."""
    async def wrapper(*args, **kwargs):
        # Extract request from args (FastAPI dependency injection)
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if request:
            limit = getattr(settings, 'rate_limit_public_per_minute', 100)
            await check_rate_limit(request, limit, "ip")

        return await func(*args, **kwargs)

    return wrapper


def authenticated_rate_limit(func):
    """Decorator for authenticated endpoints rate limiting."""
    async def wrapper(*args, **kwargs):
        # Extract request from args (FastAPI dependency injection)
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if request:
            limit = getattr(settings, 'rate_limit_authenticated_per_minute', 1000)
            await check_rate_limit(request, limit, "user")

        return await func(*args, **kwargs)

    return wrapper


class CustomRateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware wrapping :class:`SimpleRateLimiter` for FastAPI apps."""

    def __init__(
        self,
        app,
        *,
        limiter: SimpleRateLimiter | None = None,
        limit: int | None = None,
        window_seconds: int = 60,
        key_prefix: str = "ip",
    ) -> None:
        super().__init__(app)
        self._limiter = limiter or rate_limiter
        self._default_limit = limit
        self._window_seconds = window_seconds
        self._key_prefix = key_prefix

    async def dispatch(self, request: Request, call_next) -> Response:
        limit = self._default_limit
        if limit is None:
            limit = getattr(settings, "rate_limit_public_per_minute", 100)

        key = _build_rate_limit_key(request, self._key_prefix)
        allowed, remaining = await self._limiter.check_rate_limit(
            key,
            limit,
            window_seconds=self._window_seconds,
        )

        if not allowed:
            reset_time = await self._limiter.get_remaining_time(key, self._window_seconds)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(reset_time)},
            )

        if not hasattr(request.state, "rate_limit"):
            request.state.rate_limit = {}
        request.state.rate_limit.update(
            {
                "limit": limit,
                "remaining": remaining,
                "reset_time": await self._limiter.get_remaining_time(key, self._window_seconds),
            }
        )

        return await call_next(request)


__all__ = [
    "SimpleRateLimiter",
    "rate_limiter",
    "limiter",
    "check_rate_limit",
    "public_rate_limit",
    "authenticated_rate_limit",
    "CustomRateLimitMiddleware",
]


