"""
Simple rate limiter implementation for Resync API.

Uses in-memory storage for simplicity. For production, consider Redis-backed rate limiting.
"""

import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, Request
from resync.config.settings import settings


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
    if key_prefix == "ip":
        # Get client IP (simplified - in production use proper IP extraction)
        client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        key = f"ip:{client_ip}"
    elif key_prefix == "user":
        # For authenticated requests
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            key = f"user:{user_id}"
        else:
            # Fallback to IP if no user
            client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
            key = f"ip:{client_ip}"
    else:
        key = f"{key_prefix}:default"

    allowed, remaining = await rate_limiter.check_rate_limit(key, limit)

    if not allowed:
        reset_time = await rate_limiter.get_remaining_time(key)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time} seconds.",
            headers={"Retry-After": str(reset_time)}
        )

    # Store rate limit info in request state for logging
    if not hasattr(request.state, 'rate_limit'):
        request.state.rate_limit = {}
    request.state.rate_limit.update({
        'limit': limit,
        'remaining': remaining,
        'reset_time': await rate_limiter.get_remaining_time(key)
    })


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
