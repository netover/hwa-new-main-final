"""
FastAPI application factory.

This module defines a top-level ``create_app`` function which
constructs a new FastAPI application using the improved lifespan
context manager and assembles it from legacy routes and new
components.  It mounts the static file directory and templates
directory as in the original main app, includes all legacy routes
defined in ``resync.fastapi_app.main.create_app``, and registers
additional middlewares, observability endpoints and schedulers via
``register.py``.
"""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .lifespan import lifespan
from .main import create_app as legacy_create_app  # type: ignore
from .register import (
    register_middlewares,
    register_observability,
    register_routers,
    register_scheduler,
)


def create_app() -> FastAPI:
    """Assemble a new FastAPI app from legacy and modular components."""
    # Create the new application with the improved lifespan
    app = FastAPI(lifespan=lifespan)

    # Mount static files and templates as the legacy app does
    base_dir = Path(__file__).resolve().parents[2]
    static_dir = base_dir / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Expose Jinja2 templates on app.state for consistency
    templates_dir = base_dir / "templates"
    app.state.templates = Jinja2Templates(directory=str(templates_dir))  # type: ignore[attr-defined]

    # Build the legacy FastAPI app to obtain its routes and configuration
    legacy_app = legacy_create_app()
    # Include all legacy routes on the new app
    app.include_router(legacy_app.router)

    # Register additional middlewares, routers, observability and scheduler
    register_middlewares(app)
    register_routers(app)
    register_observability(app)
    register_scheduler(app)

    return app