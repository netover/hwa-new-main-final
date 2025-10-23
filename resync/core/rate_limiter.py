"""
Rate limiting utilities for the Resync application.

This module provides comprehensive rate limiting functionality using slowapi
with Redis backend, including tiered rate limiting strategies and custom
rate limit exceeded responses.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

import structlog
from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from resync.settings import settings

logger = structlog.get_logger(__name__)

from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 100
    burst_limit: int = 10
    window_size: int = 60  # seconds
    strategy: str = "moving-window"  # "moving-window" or "fixed-window"

    # Class attributes for endpoint configurations
    PUBLIC_ENDPOINTS: str = "100/minute"
    AUTHENTICATED_ENDPOINTS: str = "1000/minute"
    CRITICAL_ENDPOINTS: str = "50/minute"
    ERROR_HANDLER: str = "15/minute"
    WEBSOCKET: str = "30/minute"
    DASHBOARD: str = "10/minute"


@dataclass
class TieredRateLimitConfig:
    """Configuration for tiered rate limiting."""

    public: RateLimitConfig = None
    authenticated: RateLimitConfig = None
    critical: RateLimitConfig = None

    def __post_init__(self):
        if self.public is None:
            self.public = RateLimitConfig(requests_per_minute=100)
        if self.authenticated is None:
            self.authenticated = RateLimitConfig(requests_per_minute=1000)
        if self.critical is None:
            self.critical = RateLimitConfig(requests_per_minute=50)


def get_user_identifier(request: Request) -> str:
    """
    Get user identifier for rate limiting.
    Falls back to IP address if no user authentication is available.
    """
    # Try to get user from request state (if authentication is implemented)
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user}"

    # Fall back to IP address
    return get_remote_address(request)


def get_authenticated_user_identifier(request: Request) -> str:
    """
    Get authenticated user identifier for rate limiting.
    This should be used for endpoints that require authentication.
    """
    if hasattr(request.state, "user") and request.state.user:
        return f"auth_user:{request.state.user}"

    # For unauthenticated requests, still use IP but with different prefix
    return f"ip:{get_remote_address(request)}"


# Initialize the main rate limiter with memory storage for safety
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",  # Use memory storage to avoid configuration issues
    key_prefix="resync:ratelimit:",
    headers_enabled=True,
    strategy="moving-window",
)


def create_rate_limit_exceeded_response(
    request: Request, exc: RateLimitExceeded, retry_after: Optional[int] = None
) -> Response:
    """
    Create a custom response for rate limit exceeded errors.

    Args:
        request: The incoming request
        exc: The rate limit exceeded exception
        retry_after: Optional retry after time in seconds

    Returns:
        Custom JSON response with rate limit information
    """
    if retry_after is None:
        retry_after = exc.retry_after or 60  # Default to 60 seconds

    reset_time = datetime.utcnow() + timedelta(seconds=retry_after)

    import json

    response = Response(
        content=json.dumps(
            {
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Please try again in {retry_after} seconds.",
                "retry_after": retry_after,
                "retry_after_datetime": reset_time.isoformat() + "Z",
                "limit": exc.limit,
                "window": exc.window,
            }
        ),
        status_code=429,
        media_type="application/json",
    )

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(exc.limit)
    response.headers["X-RateLimit-Remaining"] = "0"
    response.headers["X-RateLimit-Reset"] = str(int(reset_time.timestamp()))
    response.headers["X-RateLimit-Window"] = str(exc.window)
    response.headers["Retry-After"] = str(retry_after)

    logger.warning(
        "rate_limit_exceeded",
        client_host=request.client.host,
        path=request.url.path,
        limit=exc.limit,
        window=exc.window,
        retry_after=retry_after,
    )

    return response


# Decorator functions for different endpoint categories
def public_rate_limit(func: Callable) -> Callable:
    """Decorator for public endpoints with standard rate limiting."""
    return limiter.limit(
        f"{getattr(settings, 'RATE_LIMIT_PUBLIC_PER_MINUTE', 100)}/minute"
    )(func)


def authenticated_rate_limit(func: Callable) -> Callable:
    """Decorator for authenticated endpoints with higher rate limiting."""
    return limiter.limit(
        f"{getattr(settings, 'RATE_LIMIT_AUTHENTICATED_PER_MINUTE', 1000)}/minute",
        key_func=get_authenticated_user_identifier,
    )(func)


def critical_rate_limit(func: Callable) -> Callable:
    """Decorator for critical endpoints (agents, chat) with strict rate limiting."""
    return limiter.limit(
        f"{getattr(settings, 'RATE_LIMIT_CRITICAL_PER_MINUTE', 50)}/minute",
        key_func=get_authenticated_user_identifier,
    )(func)


def error_handler_rate_limit(func: Callable) -> Callable:
    """Decorator for error handler endpoints."""
    return limiter.limit(
        f"{getattr(settings, 'RATE_LIMIT_ERROR_HANDLER_PER_MINUTE', 15)}/minute"
    )(func)


def websocket_rate_limit(func: Callable) -> Callable:
    """Decorator for WebSocket endpoints."""
    return limiter.limit(
        f"{getattr(settings, 'RATE_LIMIT_WEBSOCKET_PER_MINUTE', 30)}/minute"
    )(func)


def dashboard_rate_limit(func: Callable) -> Callable:
    """Decorator for dashboard endpoints."""
    return limiter.limit(
        f"{getattr(settings, 'RATE_LIMIT_DASHBOARD_PER_MINUTE', 10)}/minute"
    )(func)


# Custom rate limit middleware for adding headers to all responses
class CustomRateLimitMiddleware:
    """Custom rate limit middleware that adds headers to all responses."""

    def __init__(self, limiter):
        self.limiter = limiter

    async def __call__(self, request: Request, call_next):
        """Process request and add rate limit headers to response."""
        response = await call_next(request)

        # Add rate limit headers if available
        if hasattr(request.state, "rate_limit"):
            rate_limit_info = request.state.rate_limit

            response.headers["X-RateLimit-Limit"] = str(
                rate_limit_info.get("limit", "")
            )
            response.headers["X-RateLimit-Remaining"] = str(
                rate_limit_info.get("remaining", "")
            )
            response.headers["X-RateLimit-Reset"] = str(
                rate_limit_info.get("reset", "")
            )

            # Add custom headers for better client visibility
            response.headers["X-RateLimit-Policy"] = rate_limit_info.get(
                "policy", "default"
            )

        return response


def init_rate_limiter(app):
    """
    Initialize rate limiting for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Add the limiter to app state
    app.state.limiter = limiter

    # Add custom exception handler for rate limit exceeded
    app.add_exception_handler(RateLimitExceeded, create_rate_limit_exceeded_response)

    # Add custom middleware for rate limit headers
    app.add_middleware(CustomRateLimitMiddleware, limiter=limiter)

    logger.info("rate_limiting_initialized", backend="Redis")
    logger.info(
        "rate_limit_configurations",
        public=f"{getattr(settings, 'RATE_LIMIT_PUBLIC_PER_MINUTE', 100)}/minute",
        authenticated=f"{getattr(settings, 'RATE_LIMIT_AUTHENTICATED_PER_MINUTE', 1000)}/minute",
        critical=f"{getattr(settings, 'RATE_LIMIT_CRITICAL_PER_MINUTE', 50)}/minute",
    )
