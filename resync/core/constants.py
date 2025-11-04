"""
Common default constants for Resync services.

This module centralises default values used throughout the Resync
codebase to avoid scattering so‑called "magic numbers" in multiple
places.  HTTP client timeouts and connection limits, Redis pool
defaults and heuristics for incident prioritisation can all be
configured here.  Downstream modules import these constants and
override them via environment variables or application settings as
needed.

Having a single source of truth for these values makes it easier to
reason about performance characteristics and tune them without
searching for hard‑coded literals.  Values defined here represent
sensible defaults for development and small deployments; operators
should adjust them in production via the ``settings`` module or
environment variables.
"""

from __future__ import annotations

from enum import Enum

# ---------------------------------------------------------------------------
# HTTP client defaults
#
# These values are used by the HTTP client factory and lifespan to
# configure connect/read/write timeouts and connection pool limits.  They
# can be overridden by corresponding fields in the application settings
# or environment variables (e.g. ``TWS_CONNECT_TIMEOUT``).  See
# ``resync/services/http_client_factory.py`` for usage.

DEFAULT_CONNECT_TIMEOUT: float = 5.0
"""Maximum time in seconds to wait for a TCP connection to be
established when calling external services."""

DEFAULT_READ_TIMEOUT: float = 10.0
"""Maximum time in seconds to wait for a response body to be received.

This applies after the connection has been established.  Increase
this for long‑running operations such as large downloads.
"""

DEFAULT_WRITE_TIMEOUT: float = 10.0
"""Maximum time in seconds to wait when sending request data.

Write timeouts apply to the request body upload phase; they can be
increased for endpoints that accept large payloads.
"""

DEFAULT_POOL_TIMEOUT: float = 5.0
"""Maximum time in seconds to wait for a free connection from the pool.

When the connection pool is exhausted and no idle connection is
available, HTTPX will wait up to this duration for one to be
released before raising a timeout.
"""

DEFAULT_MAX_CONNECTIONS: int = 100
"""Maximum total concurrent connections allowed by the HTTP client.

This limit prevents unbounded growth of sockets and ensures the
application behaves predictably under load.  Tune according to
expected concurrency and resources.
"""

DEFAULT_MAX_KEEPALIVE_CONNECTIONS: int = 20
"""Maximum number of idle keepalive connections to maintain.

Keeping some connections alive improves performance by reusing
TCP/TLS handshakes but too many idle connections waste resources.
"""

# ---------------------------------------------------------------------------
# Redis defaults
#
# These values mirror the defaults used in ``resync/core/redis_factory.py``.
# They are exposed here so that other modules (e.g. documentation or
# testing harnesses) can import and reference them without touching
# Redis directly.

DEFAULT_REDIS_MAX_CONNECTIONS: int = 50
DEFAULT_REDIS_CONNECT_TIMEOUT: float = 5.0
DEFAULT_REDIS_SOCKET_TIMEOUT: float = 3.0
DEFAULT_REDIS_HEALTH_CHECK_INTERVAL: int = 30

# ---------------------------------------------------------------------------
# Incident prioritisation heuristics
#
# The following weights are used to compute priority scores for
# incidents based on status and queue length.  They can be tuned to
# adjust the relative importance of different failure modes.  See
# ``resync/fastapi_app/main.py`` for usage.

RISK_WEIGHT_ABEND: float = 1.5
"""Weight multiplier applied to incidents with ABEND status."""

RISK_WEIGHT_QUEUE: float = 2.0
"""Weight multiplier applied to incidents queued for execution."""


class ErrorMessages(str, Enum):
    """Standardized error message templates for API responses."""

    TIMEOUT = "{operation} timed out: {detail}"
    CONNECTION = "{operation} failed due to connection issues: {detail}"
    AUTH_REQUIRED = "{operation} requires authentication."
    UNAUTHORIZED = "Unauthorized to perform {operation}."
    FORBIDDEN = "{operation} is forbidden."
    NOT_FOUND = "{operation} resource was not found."
    VALIDATION_ERROR = "Validation error in {operation}: {detail}"
    CONFLICT = "Conflict while performing {operation}: {detail}"
    SERVICE_UNAVAILABLE = "{operation} is temporarily unavailable. Try again later."
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded during {operation}. Please retry later."
    QUOTA_EXCEEDED = "Quota exceeded during {operation}. Please contact support."
    INTERNAL_ERROR = "Unexpected error during {operation}: {detail}"


__all__ = [
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_READ_TIMEOUT",
    "DEFAULT_WRITE_TIMEOUT",
    "DEFAULT_POOL_TIMEOUT",
    "DEFAULT_MAX_CONNECTIONS",
    "DEFAULT_MAX_KEEPALIVE_CONNECTIONS",
    "DEFAULT_REDIS_MAX_CONNECTIONS",
    "DEFAULT_REDIS_CONNECT_TIMEOUT",
    "DEFAULT_REDIS_SOCKET_TIMEOUT",
    "DEFAULT_REDIS_HEALTH_CHECK_INTERVAL",
    "RISK_WEIGHT_ABEND",
    "RISK_WEIGHT_QUEUE",
    "ErrorMessages",
]
