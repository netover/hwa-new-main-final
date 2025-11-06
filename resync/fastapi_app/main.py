"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from .config.middleware import setup_middleware  # type: ignore
from .config.static import setup_static_files  # type: ignore
from .lifespan import lifespan  # type: ignore
from .routes import register_routes  # type: ignore


def create_app() -> FastAPI:
    """Create FastAPI application with proper type annotations."""
    app: FastAPI = FastAPI(
        title="Resync API",
        description="Unified API for Resync TWS Integration",
        version="1.0.0",
        lifespan=lifespan,
    )
    setup_middleware(app)
    setup_static_files(app)
    register_routes(app)
    return app


app = create_app()
