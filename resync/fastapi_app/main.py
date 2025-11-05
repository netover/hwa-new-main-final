"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from .config.middleware import setup_middleware

# Initialise structured logging on import.  This ensures that
# structlog is configured with JSON rendering and contextual
# processors before the application is constructed.  The import
# executes configuration immediately and does not pollute the global
# namespace.
try:
    import config.structured_logging  # noqa: F401
except Exception:
    # Logging configuration not available; continue without structured logs
    pass
from .config.static import setup_static_files
from .lifespan import lifespan
from .routes import register_routes

def create_app() -> FastAPI:
    app = FastAPI(
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
