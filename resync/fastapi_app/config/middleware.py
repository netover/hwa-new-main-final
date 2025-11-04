"""Middleware configuration helpers for the FastAPI application."""

from __future__ import annotations

import os
from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resync.api.middleware.correlation_id import CorrelationIdMiddleware

from ..middleware.metrics import MetricsMiddleware
from .app_state import initialize_state

try:
    from resync.api.exception_handlers import register_exception_handlers
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
        register_exception_handlers(app)
