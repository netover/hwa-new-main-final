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

import logging
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

logger = logging.getLogger(__name__)


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
    neo4j_driver: Optional[object] = None

    # ------------------------------------------------------------------
    # Validate and summarise environment configuration.  If required
    # variables are missing or malformed, fallback defaults are used and
    # a warning is logged.  A summary of the resolved configuration
    # values is emitted to aid troubleshooting and ensure operators are
    # aware of the active runtime configuration.
    env_summary = {}
    # Redis configuration
    redis_url = os.getenv("REDIS_URL", os.getenv("REDIS_URI", "redis://localhost:6379/0"))
    env_summary["REDIS_URL"] = redis_url
    redis_max_conn = os.getenv("REDIS_MAX_CONNECTIONS", None)
    try:
        redis_max_conn_int = int(redis_max_conn) if redis_max_conn is not None else None
    except Exception:
        logger.warning(
            "Invalid REDIS_MAX_CONNECTIONS value '%s'; using default", redis_max_conn
        )
        redis_max_conn_int = None
    env_summary["REDIS_MAX_CONNECTIONS"] = redis_max_conn_int

    # HTTPX/HTTP client configuration
    http_max_conn = os.getenv("HTTP_MAX_CONNECTIONS", None)
    try:
        http_max_conn_int = int(http_max_conn) if http_max_conn is not None else None
    except Exception:
        logger.warning(
            "Invalid HTTP_MAX_CONNECTIONS value '%s'; using default", http_max_conn
        )
        http_max_conn_int = None
    env_summary["HTTP_MAX_CONNECTIONS"] = http_max_conn_int

    # Neo4j configuration
    neo4j_uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")
    env_summary["NEO4J_URI"] = neo4j_uri
    env_summary["NEO4J_USER"] = neo4j_user
    env_summary["NEO4J_PASSWORD_SET"] = bool(neo4j_password)
    kg_backend = os.getenv("KG_BACKEND", "stub").lower()
    env_summary["KG_BACKEND"] = kg_backend

    # Log environment summary at INFO level once on startup
    try:
        logger.info(
            "Application configuration", extra={"config": env_summary}
        )
    except Exception:
        # Do not crash startup due to logging failure
        pass
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
            logger.exception("Failed to create Redis client during startup")
            redis_client = None

    # Create a shared HTTP client when httpx is available.  Use sensible
    # timeouts and connection limits from constants.  This client
    # supports HTTP/1.1 and HTTP/2 and will be reused for outbound
    # network calls throughout the app.  If httpx is unavailable the
    # application will operate without a shared client.
    if httpx is not None:
        try:
            http_client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(
                    DEFAULT_READ_TIMEOUT,
                    connect=DEFAULT_CONNECT_TIMEOUT,
                    read=DEFAULT_READ_TIMEOUT,
                    write=DEFAULT_WRITE_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT,
                ),
                limits=httpx.Limits(
                    max_connections=DEFAULT_MAX_CONNECTIONS,
                    max_keepalive_connections=DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
                    keepalive_expiry=30.0,
                ),
                follow_redirects=True,
            )
            app.state.http = http_client  # type: ignore[attr-defined]
            app.state.http_client = http_client  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to create shared HTTPX client during startup")
            http_client = None

    # Create a shared Neo4j driver when available so the connection pool
    # can be reused by request handlers.  The driver is stored on
    # ``app.state`` for dependency injection and closed on shutdown.
    try:
        from neo4j import AsyncGraphDatabase  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        AsyncGraphDatabase = None  # type: ignore

    if AsyncGraphDatabase is not None:
        neo4j_uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        try:
            neo4j_driver = AsyncGraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
            )
            app.state.neo4j = neo4j_driver  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to initialise Neo4j driver")
            neo4j_driver = None

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
                logger.exception("Failed to ensure Neo4j indexes; falling back to stub backend")
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
                logger.exception("Error while closing shared HTTPX client during shutdown")
                pass
        # Close Redis client if created
        if redis_client is not None:
            try:
                await redis_client.aclose()  # type: ignore[no-untyped-call]
            except Exception:
                logger.exception("Error while closing Redis client during shutdown")
                pass
        if neo4j_driver is not None:
            try:
                await neo4j_driver.close()  # type: ignore[no-untyped-call]
            except Exception:
                logger.exception("Error while closing Neo4j driver during shutdown")
        # Shut down any TWS HTTPX clients
        try:
            await shutdown_httpx()
        except Exception:
            logger.exception("Error while shutting down TWS HTTPX client")
            pass
