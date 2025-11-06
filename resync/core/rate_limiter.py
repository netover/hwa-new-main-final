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

from resync.settings.settings import settings

# Import runtime metrics lazily to avoid circular dependencies.  When
# monitoring is unavailable the import will fail silently.
try:
    from resync.core.monitoring.metrics import runtime_metrics  # type: ignore[attr-defined]
except Exception:
    runtime_metrics = None  # type: ignore
from resync.utils.simple_logger import get_logger

# Third party imports used for compatibility with the real slowapi API. When
# the actual ``slowapi`` package is not installed, the local ``slowapi``
# shim defined in ``project/slowapi`` will be used instead. This shim
# provides a ``Limiter`` class and a ``RateLimitExceeded`` exception with
# minimal behaviour sufficient for the test suite.
from slowapi import Limiter  # type: ignore[attr-defined]
from slowapi.errors import RateLimitExceeded  # type: ignore[attr-defined]

import inspect
from typing import Callable, Any


logger = get_logger(__name__)


class RateLimitConfig:
    """Default rate limit strings for various endpoint categories."""

    PUBLIC_ENDPOINTS = "100/minute"
    AUTHENTICATED_ENDPOINTS = "1000/minute"
    CRITICAL_ENDPOINTS = "50/minute"
    ERROR_HANDLER = "15/minute"
    WEBSOCKET = "30/minute"
    DASHBOARD = "10/minute"


# When the slowapi library is available, this will reference its Limiter
# instance. In our environment we import the shim from ``slowapi`` so
# that the type annotation resolves correctly. Tests inspect this
# variable indirectly via ``init_rate_limiter``.
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
        # Increment rate limit hit counter when monitoring is enabled
        if runtime_metrics is not None:
            try:
                runtime_metrics.rate_limit_hits_total.increment()
            except Exception:
                pass
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
            # Record rate limit violation in metrics
            if runtime_metrics is not None:
                try:
                    runtime_metrics.rate_limit_hits_total.increment()
                except Exception:
                    pass
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


# ---------------------------------------------------------------------------
# User identifier helpers
# ---------------------------------------------------------------------------

def get_user_identifier(request: Any) -> str:
    """Return a string uniquely identifying the caller for rate limiting.

    The identifier is derived from the request state and client address.
    If the request carries an authenticated user (``request.state.user``), the
    identifier will be prefixed with ``"user:"``. Otherwise, the client IP
    address is returned directly. If neither are available the string
    ``"unknown"`` is returned.  ``Any`` is accepted for the ``request`` type
    to make this helper robust against poorly mocked objects during tests.
    """
    try:
        # Prefer an authenticated user if present
        user = getattr(request.state, "user", None)
        if user:
            return f"user:{user}"
    except Exception:
        # If request.state is missing or inaccessible, fall back to client IP
        pass
    # Attempt to return the client host
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return host if host is not None else "unknown"


def get_authenticated_user_identifier(request: Any) -> str:
    """Return a string identifying the caller for authenticated rate limits.

    If an authenticated user is present on ``request.state.user``, the result
    is prefixed with ``"auth_user:"``. Otherwise the client IP is returned
    prefixed with ``"ip:"`` when available. If neither are available,
    ``"unknown"`` is returned.
    """
    try:
        user = getattr(request.state, "user", None)
        if user:
            return f"auth_user:{user}"
    except Exception:
        pass
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return f"ip:{host}" if host is not None else "unknown"


# ---------------------------------------------------------------------------
# Rate limit exceeded response
# ---------------------------------------------------------------------------

def create_rate_limit_exceeded_response(
    request: Request, exc: RateLimitExceeded
) -> Response:
    """Build a JSON response for a rate limit exceeded exception.

    This helper centralizes the formatting of rate limit violation messages.
    It sets status code 429 (Too Many Requests), includes headers to
    communicate the limit, remaining quota and retry delay, and exposes a
    ``content`` attribute containing the dictionary for tests that rely on
    direct access to the parsed JSON. When ``exc.retry_after`` is ``None``
    the ``exc.window`` attribute is used as a fallback; if that is also
    ``None`` a default of ``1`` second is used.
    """
    # Determine how many seconds the client should wait before retrying
    retry_after: int
    if exc.retry_after is not None:
        retry_after = int(exc.retry_after)
    elif exc.window is not None:
        retry_after = int(exc.window)
    else:
        retry_after = 1
    # Build response payload
    payload = {"error": "Rate limit exceeded", "retry_after": retry_after}
    response = JSONResponse(status_code=429, content=payload)
    # Expose a ``content`` attribute on the response for tests expecting it
    # Note: the built-in JSONResponse does not normally set ``content``.
    setattr(response, "content", payload)
    # Set standard rate limiting headers
    # Limit may be None on the exception; convert to empty string in that case
    response.headers["X-RateLimit-Limit"] = (
        str(exc.limit) if exc.limit is not None else ""
    )
    # When a limit is exceeded there are no remaining requests
    response.headers["X-RateLimit-Remaining"] = "0"
    response.headers["Retry-After"] = str(retry_after)
    return response


# ---------------------------------------------------------------------------
# Rate limit decorators
# ---------------------------------------------------------------------------

def _decorate_with_rate_limit(
    func: Callable[..., Any],
    limit_str: str,
    limit_value: int,
    key_prefix: str,
) -> Callable[..., Any]:
    """Internal helper to build a rate limiting decorator.

    This function accepts a target ``func`` and returns a wrapper that
    optionally enforces a limit using :func:`check_rate_limit` when the
    decorated function is asynchronous. For synchronous functions no
    enforcement is performed, matching the behaviour of the shim version
    of slowapi's limiter. In both cases the returned wrapper is annotated
    with a ``_rate_limit`` attribute storing the human‑readable limit
    string (e.g. ``"100/minute"``) for test inspection.
    """
    # Determine if the function is a coroutine
    is_coroutine = bool(func.__code__.co_flags & 0x80)
    if is_coroutine:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract a Request instance if present among positional args
            request_obj: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request_obj = arg
                    break
            # Enforce the rate limit if we have a request
            if request_obj is not None:
                await check_rate_limit(request_obj, limit_value, key_prefix)
            return await func(*args, **kwargs)

        wrapper = async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # We do not enforce asynchronous rate limiting for synchronous
            # callables. The simple limiter cannot be awaited in a sync
            # context. This matches the behaviour of the shim where
            # synchronous functions are not rate limited by default.
            return func(*args, **kwargs)

        wrapper = sync_wrapper  # type: ignore[assignment]
    # Attach metadata for tests
    setattr(wrapper, "_rate_limit", limit_str)
    return wrapper


def public_rate_limit(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator applying the public endpoint rate limit.

    When the decorated function is asynchronous and a :class:`Request`
    instance is present as the first or second positional argument, this
    decorator will invoke :func:`check_rate_limit` using the public
    configuration from :mod:`resync.config.settings`. The wrapper
    exposes a ``_rate_limit`` attribute equal to
    :data:`RateLimitConfig.PUBLIC_ENDPOINTS` for test inspection.
    """
    limit_value = getattr(settings, "rate_limit_public_per_minute", 100)
    return _decorate_with_rate_limit(
        func,
        RateLimitConfig.PUBLIC_ENDPOINTS,
        limit_value,
        "ip",
    )


def authenticated_rate_limit(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator applying the authenticated endpoint rate limit.

    Similar to :func:`public_rate_limit` but uses the authenticated rate
    limit from settings and identifies callers by user when available.
    """
    limit_value = getattr(settings, "rate_limit_authenticated_per_minute", 1000)
    return _decorate_with_rate_limit(
        func,
        RateLimitConfig.AUTHENTICATED_ENDPOINTS,
        limit_value,
        "user",
    )


def critical_rate_limit(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator applying the critical endpoint rate limit.

    Critical endpoints often involve operations that must be protected
    more aggressively. The limit applied here comes from
    ``settings.rate_limit_critical_per_minute`` with a default of 50
    requests per minute. The key prefix ``"ip"`` is used since these
    endpoints may or may not require authentication. Tests expect the
    wrapper to expose the string stored in
    :data:`RateLimitConfig.CRITICAL_ENDPOINTS` via a ``_rate_limit``
    attribute.
    """
    limit_value = getattr(settings, "rate_limit_critical_per_minute", 50)
    return _decorate_with_rate_limit(
        func,
        RateLimitConfig.CRITICAL_ENDPOINTS,
        limit_value,
        "ip",
    )


# ---------------------------------------------------------------------------
# Rate limiter initialization
# ---------------------------------------------------------------------------

def init_rate_limiter(app: Any) -> None:
    """Initialize rate limiting on a FastAPI application.

    This function configures a global ``Limiter`` instance, registers an
    exception handler for :class:`RateLimitExceeded`, and adds the
    :class:`CustomRateLimitMiddleware` to the application. A reference
    to the limiter is stored on ``app.state.limiter``. The implementation
    gracefully handles the absence of an external Redis backend by
    falling back to the in-memory ``SimpleRateLimiter``. A log message
    is emitted via the module logger to indicate completion.
    """
    # Use the imported Limiter class (shim or real) to create a limiter.
    # We derive a key function for the real slowapi limiter using our
    # authenticated identifier helper. When the shim is used this is
    # ignored.
    key_func: Callable[[Any], str] = get_authenticated_user_identifier
    default_limits = [RateLimitConfig.ERROR_HANDLER]
    try:
        # Attempt to configure a Redis storage URI if available.
        storage_uri = getattr(settings, "redis_url", None) or getattr(settings, "REDIS_URL", None)
        limiter = Limiter(key_func=key_func, default_limits=default_limits, storage_uri=storage_uri)
    except Exception:
        # In case the Limiter could not be instantiated (e.g. wrong
        # constructor signature), fall back to a minimal instance.
        limiter = Limiter(key_func=key_func)
    # Expose the limiter on the application state for other components
    try:
        app.state.limiter = limiter  # type: ignore[assignment]
    except Exception:
        # If state is missing, attach an empty object and set the attribute
        if not hasattr(app, "state"):
            class _State:  # pragma: no cover - extremely unlikely path
                pass
            app.state = _State()
        app.state.limiter = limiter  # type: ignore[assignment]
    # Register an exception handler for RateLimitExceeded. The handler
    # delegates to our response factory which returns a JSONResponse.
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
        return create_rate_limit_exceeded_response(request, exc)
    try:
        app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[attr-defined]
    except Exception:
        # Some frameworks may store exception handlers in a dict directly
        try:
            app.exception_handlers[RateLimitExceeded] = rate_limit_handler  # type: ignore[index]
        except Exception:
            pass
    # Add the custom middleware to apply rate limiting automatically. When
    # using the shim version of the limiter this will still attach rate
    # limit information to ``request.state.rate_limit`` but will not
    # enforce remote limits.
    try:
        app.add_middleware(CustomRateLimitMiddleware, limiter=rate_limiter)  # type: ignore[attr-defined]
    except Exception:
        # If middleware cannot be added (e.g. not a FastAPI app), ignore.
        pass
    # Store reference in module-level for introspection if desired
    global _slowapi_limiter
    _slowapi_limiter = limiter  # type: ignore[assignment]
    # Log initialization
    try:
        logger.info("Rate limiter initialized")  # type: ignore[call-arg]
    except Exception:
        pass


__all__ = [
    "SimpleRateLimiter",
    "rate_limiter",
    "limiter",
    "check_rate_limit",
    "public_rate_limit",
    "authenticated_rate_limit",
    "critical_rate_limit",
    "get_user_identifier",
    "get_authenticated_user_identifier",
    "create_rate_limit_exceeded_response",
    "init_rate_limiter",
    "CustomRateLimitMiddleware",
]






