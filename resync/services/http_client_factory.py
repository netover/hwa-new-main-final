"""
HTTP client factory for creating configured httpx.AsyncClient instances.

This module provides a centralized way to create HTTP clients with
consistent configuration, timeouts, and limits across the application.
"""

from typing import Optional

import httpx
from httpx import AsyncClient

from resync.core.constants import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    DEFAULT_POOL_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
)
from resync.settings import settings


def create_async_http_client(
    base_url: str,
    auth: Optional[httpx.BasicAuth] = None,
    verify: bool = True,
    connect_timeout: Optional[float] = None,
    read_timeout: Optional[float] = None,
    write_timeout: Optional[float] = None,
    pool_timeout: Optional[float] = None,
    max_connections: Optional[int] = None,
    max_keepalive: Optional[int] = None,
) -> httpx.AsyncClient:
    """
    Creates a configured httpx.AsyncClient with sensible defaults.

    Provides centralized HTTP client configuration with override capabilities
    for specific use cases while maintaining consistent defaults.

    Args:
        base_url: Base URL for the client
        auth: Optional authentication credentials
        verify: Whether to verify SSL certificates (default: True)
        connect_timeout: Override default connect timeout
        read_timeout: Override default read timeout
        write_timeout: Override default write timeout
        pool_timeout: Override default pool timeout
        max_connections: Override default max connections
        max_keepalive: Override default max keepalive connections

    Returns:
        Configured httpx.AsyncClient instance with proper timeouts and limits

    Example:
        ```python
        client = create_async_http_client(
            base_url="https://api.example.com",
            auth=httpx.BasicAuth("user", "pass"),
            connect_timeout=5.0
        )
        ```
    """
    return httpx.AsyncClient(
        base_url=base_url,
        auth=auth,
        verify=verify,
        timeout=httpx.Timeout(
            connect=connect_timeout
            or getattr(settings, "TWS_CONNECT_TIMEOUT", DEFAULT_CONNECT_TIMEOUT),
            read=read_timeout
            or getattr(settings, "TWS_READ_TIMEOUT", DEFAULT_READ_TIMEOUT),
            write=write_timeout
            or getattr(settings, "TWS_WRITE_TIMEOUT", DEFAULT_WRITE_TIMEOUT),
            pool=pool_timeout
            or getattr(settings, "TWS_POOL_TIMEOUT", DEFAULT_POOL_TIMEOUT),
        ),
        limits=httpx.Limits(
            max_connections=max_connections
            or getattr(settings, "TWS_MAX_CONNECTIONS", DEFAULT_MAX_CONNECTIONS),
            max_keepalive_connections=max_keepalive
            or getattr(
                settings, "TWS_MAX_KEEPALIVE", DEFAULT_MAX_KEEPALIVE_CONNECTIONS
            ),
        ),
    )


import logging

logger = logging.getLogger(__name__)

def create_tws_http_client(*, base_url: str | None = None, auth=None, verify: bool | str | None = None, **kwargs) -> AsyncClient:
    scheme = settings.TWS_SCHEME
    host = settings.TWS_HOST
    port = settings.TWS_PORT
    final_base = base_url or f"{scheme}://{host}:{port}"
    # Enforce TWS-specific verification setting
    verify_param = settings.TWS_VERIFY if verify is None else verify

    # ... timeout and limits config ...
    return AsyncClient(
        base_url=final_base,
        auth=auth,
        timeout=timeout,
        limits=limits,
        verify=verify_param,  # Apply TWS verification setting
        **kwargs
    )
