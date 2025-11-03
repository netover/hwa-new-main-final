"""
Centralized Redis client factory.

This module exposes a single ``create_redis`` function that returns a
configured ``redis.asyncio.Redis`` client using sensible defaults.  It
applies connection timeouts, socket keepalive options and connection
pool sizing parameters in one place.  Downstream code should import
and call this function rather than instantiating Redis clients
directly.  The resulting client uses UTF‑8 encoding and returns
strings instead of bytes.

The defaults can be overridden via environment variables:

* ``REDIS_URL`` – connection URL (default: ``redis://localhost:6379/0``)
* ``REDIS_MAX_CONNECTIONS`` – maximum pool size (default: 50)
* ``REDIS_CONNECT_TIMEOUT`` – connection timeout in seconds (default: 5)
* ``REDIS_SOCKET_TIMEOUT`` – read/write timeout in seconds (default: 3)
* ``REDIS_HEALTH_CHECK_INTERVAL`` – health check interval in seconds (default: 30)

For platform portability the TCP keepalive options are only applied
when supported by the underlying operating system.  Callers must
explicitly close the returned client via ``await client.aclose()`` when
shutting down the application to avoid dangling connections.
"""

from __future__ import annotations

import os
import socket
from typing import Optional

try:
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover - redis is optional
    redis = None  # type: ignore


def _keepalive_opts() -> Optional[dict[int, int]]:
    """Construct TCP keepalive options if supported by the OS.

    Returns a mapping from socket option constants to values or ``None``
    when no keepalive parameters can be set.  This helper gracefully
    degrades on platforms where keepalive attributes are missing.
    """
    mapping = {"TCP_KEEPIDLE": 60, "TCP_KEEPINTVL": 10, "TCP_KEEPCNT": 3}
    opts: dict[int, int] = {}
    for name, val in mapping.items():
        if hasattr(socket, name):
            opts[getattr(socket, name)] = val
    return opts or None


def create_redis(url: str | None = None) -> "redis.Redis":  # type: ignore
    """Create a new ``redis.asyncio.Redis`` client with pooling and timeouts.

    The returned client uses UTF‑8 encoding and string responses.  It is
    configured with sensible defaults for connection limits and timeouts.

    Args:
        url: Optional connection URL.  When ``None`` the ``REDIS_URL``
            environment variable or a sane default is used.

    Returns:
        A configured ``redis.asyncio.Redis`` client instance.

    Raises:
        RuntimeError: When the ``redis`` package is not installed.
    """
    if redis is None:
        raise RuntimeError(
            "redis-py is not installed; install redis>=5.0 to enable Redis support"
        )

    conn_url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")

    max_conns = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
    connect_timeout = float(os.getenv("REDIS_CONNECT_TIMEOUT", "5"))
    socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", "3"))
    health_check_interval = int(
        os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")
    )

    return redis.from_url(  # type: ignore[no-any-return]
        conn_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=max_conns,
        socket_connect_timeout=connect_timeout,
        socket_timeout=socket_timeout,
        health_check_interval=health_check_interval,
        socket_keepalive=True,
        socket_keepalive_options=_keepalive_opts(),
        retry_on_timeout=True,
    )