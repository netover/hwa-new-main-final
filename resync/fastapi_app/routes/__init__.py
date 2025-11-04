"""Registration helpers for FastAPI route modules."""

from __future__ import annotations

from fastapi import FastAPI

from . import core, rag, observability, incidents, reports, tws, admin


def register_routes(app: FastAPI) -> None:
    """Attach all application routers to the FastAPI instance."""
    app.include_router(core.router)
    app.include_router(rag.router)
    app.include_router(observability.router)
    app.include_router(incidents.router)
    app.include_router(reports.router)
    app.include_router(tws.router)
    app.include_router(admin.router)
    admin.setup(app)
