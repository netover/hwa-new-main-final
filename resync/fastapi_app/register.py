"""
Application registration helpers.

This module provides helper functions to register middlewares,
routers, observability endpoints and schedulers on a FastAPI
application instance.  It is intended to be used by the top-level
``create_app`` factory to assemble the application from its
constituent parts.

The registration functions are designed to be idempotent and
lightweight.  They import and configure components lazily to avoid
cyclic imports.
"""

from __future__ import annotations

from fastapi import FastAPI


def register_middlewares(app: FastAPI) -> None:
    """Register application-wide middlewares.

    This currently registers a correlation ID middleware to ensure
    requests and responses carry a consistent ``X-Correlation-ID``.  It
    also attaches custom exception handlers if available in
    ``resync.api.exception_handlers``.  The CORS middleware is not
    included here because legacy configuration in ``main.py`` already
    applies it; if desired, CORS can be centralized here instead.
    """
    try:
        # Correlation ID middleware (ASGI version)
        from resync.api.middleware.correlation_id import CorrelationIdMiddleware  # type: ignore

        app.add_middleware(CorrelationIdMiddleware)
    except Exception:
        # Ignore if middleware cannot be imported
        pass

    try:
        # Register custom exception handlers if available
        from resync.api.exception_handlers import register_exception_handlers  # type: ignore

        register_exception_handlers(app)
    except Exception:
        # Ignore if exception handlers cannot be imported
        pass


def register_routers(app: FastAPI) -> None:
    """Register additional routers on the application.

    Currently this function is a placeholder.  The legacy routes from
    ``resync.fastapi_app.main.create_app()`` are included directly
    by the app factory, so there is no need to register extra routers
    here unless new modular routers are implemented.
    """
    # Example of including a separate router module:
    # from resync.api.routers.reports import router as reports_router
    # app.include_router(reports_router, prefix="/api/v1")
    return None


def register_observability(app: FastAPI) -> None:
    """Register observability endpoints (metrics, health) on the app.

    This function exposes a simple ``/metrics`` endpoint that forwards
    to the legacy observability route defined in ``main.py`` if
    available.  A real implementation would integrate Prometheus
    counters/histograms here.
    """
    # No-op placeholder; legacy metrics routes remain accessible via
    # inclusion of legacy routes on the new app.
    return None


def register_scheduler(app: FastAPI) -> None:
    """Start the optional scheduler for background jobs.

    If APScheduler is installed and a scheduler is not already running
    on the application state, this function will create a new
    AsyncIOScheduler and start it.  No jobs are scheduled by default.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
    except Exception:
        # APScheduler not installed; skip scheduler setup
        return None

    # Avoid starting multiple schedulers
    if getattr(app.state, "scheduler", None):
        return None

    scheduler = AsyncIOScheduler()
    # Add background jobs here if needed, for example:
    # scheduler.add_job(func, trigger="interval", minutes=5)
    scheduler.start()
    app.state.scheduler = scheduler  # type: ignore[attr-defined]