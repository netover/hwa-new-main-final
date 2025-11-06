"""Middleware configuration helpers for the FastAPI application."""

from __future__ import annotations

import os
from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resync.api.middleware.correlation_id import CorrelationIdMiddleware

from ..middleware.metrics import MetricsMiddleware
from .app_state import initialize_state

# Import rate limiter initialization. This hooks up a single instance of
# SlowAPI's Limiter and installs the associated exception handler and
# middleware. The call to ``init_rate_limiter`` should occur once at
# application startup to avoid multiple limiters being created. See
# ``resync/core/rate_limiter.py`` for details.
try:
    from resync.core.rate_limiter import init_rate_limiter  # type: ignore[attr-defined]  # noqa: E501
except Exception:
    # If the rate limiter is unavailable the application will run
    # without rate limiting. This can occur in minimal test
    # environments where the slowapi shim is not installed.
    init_rate_limiter = None  # type: ignore

try:
    from resync.api.exception_handlers import register_exception_handlers  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    register_exception_handlers = None  # type: ignore


def _allowed_origins_from_env() -> Sequence[str]:
    origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if not origins:
        return ["*"]
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def setup_middleware(app: FastAPI) -> None:
    """Initialise application state and register shared middlewares."""
    initialize_state(app)

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_allowed_origins_from_env()),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if register_exception_handlers:
        register_exception_handlers(app)  # type: ignore

    # Initialize a global rate limiter. When available this configures a
    # single Limiter instance and adds the CustomRateLimitMiddleware
    # provided by ``resync.core.rate_limiter``. If the init function
    # could not be imported the application simply proceeds without
    # rate limiting.
    if callable(init_rate_limiter):
        try:
            init_rate_limiter(app)
        except Exception:
            # Log and continue to avoid failing middleware setup due to
            # rate limiter misconfiguration. The logger is obtained
            # lazily to minimise overhead if logging is not configured.
            import logging
            logging.getLogger(__name__).exception(
                "Failed to initialize rate limiter during middleware setup"
            )
