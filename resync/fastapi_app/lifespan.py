"""
Application lifespan management for FastAPI.

This module defines an ``asynccontextmanager`` function that sets up
shared resources on application startup and tears them down on
shutdown.  It centralises creation of a Redis client using
``resync.core.redis_factory.create_redis`` and stores it on
``app.state`` for reuse throughout the application.  During shutdown
the Redis client is gracefully closed.  In addition, if the
``resync.services.tws_service.shutdown_httpx`` function is available it
will be invoked to close any HTTPX clients used by the TWS service.

Importing this module does not have side effects; the context manager
is only executed when FastAPI invokes it as part of the lifespan
workflow.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import os

from fastapi import FastAPI

try:
    # Import our Redis factory.  When Redis support is unavailable the
    # factory will be ``None`` and no Redis client will be created.
    from resync.core.redis_factory import create_redis  # type: ignore
except Exception:
    create_redis = None  # type: ignore

try:
    # TWS service exposes a shutdown routine for its HTTPX client
    from resync.services.tws_service import shutdown_httpx  # type: ignore
except Exception:
    async def shutdown_httpx() -> None:  # type: ignore
        """Fallback shutdown routine when TWS service is unavailable."""
        return None

# Attempt to import a Neo4j bootstrapper.  When Neo4j support is not
# enabled the import will fail silently.  The bootstrap routine
# ensures indexes and constraints are created idempotently on
# application startup.
try:
    from resync.core.neo4j_bootstrap import ensure_indexes  # type: ignore
except Exception:
    ensure_indexes = None  # type: ignore

# Import HTTPX lazily.  If the library is missing the application
# will operate without a shared HTTP client.  Endpoints that need
# HTTPX should instantiate their own clients or use the TWS client
try:
    import httpx  # type: ignore
except Exception:
    httpx = None  # type: ignore

# Import constants for default timeouts and pool sizes
try:
    from resync.core.constants import (
        DEFAULT_CONNECT_TIMEOUT,
        DEFAULT_READ_TIMEOUT,
        DEFAULT_WRITE_TIMEOUT,
        DEFAULT_POOL_TIMEOUT,
        DEFAULT_MAX_CONNECTIONS,
        DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    )
except Exception:
    # Fallback defaults if constants are unavailable
    DEFAULT_CONNECT_TIMEOUT = 5.0  # type: ignore
    DEFAULT_READ_TIMEOUT = 10.0  # type: ignore
    DEFAULT_WRITE_TIMEOUT = 10.0  # type: ignore
    DEFAULT_POOL_TIMEOUT = 5.0  # type: ignore
    DEFAULT_MAX_CONNECTIONS = 100  # type: ignore
    DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 20  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # type: ignore[async-yield-type]
    """Manage application startup and shutdown.

    On startup this context manager will create a Redis client (if
    ``create_redis`` is available) and attach it to ``app.state``.  Any
    exceptions during creation will be silently ignored.  On shutdown
    the Redis client is closed and the TWS HTTPX client shutdown
    routine is called.

    Args:
        app: The FastAPI application instance.

    Yields:
        ``None`` to allow the application to run.
    """
    redis_client: Optional[object] = None
    http_client: Optional[object] = None
    # ----------------------------------------------------------------------
    # Startup: initialise shared resources
    #
    # Create a Redis client if redis support is enabled.  The client
    # returned by create_redis manages its own connection pool and is safe
    # to reuse across the application.  Store it on app.state for
    # dependency injection.
    if callable(create_redis):
        try:
            redis_client = create_redis()
            app.state.redis = redis_client  # type: ignore[attr-defined]
        except Exception:
            redis_client = None

    # Create a shared HTTP client when httpx is available.  Use sensible
    # timeouts and connection limits from constants.  This client
    # supports HTTP/1.1 and HTTP/2 and will be reused for outbound
    # network calls throughout the app.  If httpx is unavailable the
    # application will operate without a shared client.
    if httpx is not None:
        try:
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=DEFAULT_READ_TIMEOUT,
                    write=DEFAULT_WRITE_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT,
                ),
                limits=httpx.Limits(
                    max_connections=DEFAULT_MAX_CONNECTIONS,
                    max_keepalive_connections=DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
                ),
                http2=True,
            )
            app.state.http_client = http_client  # type: ignore[attr-defined]
        except Exception:
            http_client = None

    # If the Neo4j backend is enabled via KG_BACKEND=neo4j then
    # idempotently ensure indexes and constraints exist.  If the
    # bootstrapper is unavailable this step is skipped.
    if ensure_indexes is not None:
        backend = os.getenv("KG_BACKEND", "stub").lower()
        if backend == "neo4j":
            try:
                await ensure_indexes()
                app.state.kg_backend = "neo4j"  # type: ignore[attr-defined]
            except Exception:
                # Keep stub fallback; do not fail startup
                app.state.kg_backend = "stub"  # type: ignore[attr-defined]

    try:
        # Yield control back to FastAPI to serve requests
        yield
    finally:
        # ------------------------------------------------------------------
        # Shutdown: gracefully close shared resources
        #
        # Close HTTPX client if one was created
        if http_client is not None:
            try:
                await http_client.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                pass
        # Close Redis client if created
        if redis_client is not None:
            try:
                await redis_client.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                pass
        # Shut down any TWS HTTPX clients
        try:
            await shutdown_httpx()
        except Exception:
            pass