"""
Async scheduler integration using APScheduler.

This module exposes a helper to start a scheduler for background
tasks on a FastAPI application.  It uses the ``apscheduler``
``AsyncIOScheduler`` to allow periodic jobs to run alongside the
ASGI event loop.

Jobs are not added by default; downstream modules should import
``maybe_start_scheduled_jobs`` and register their own jobs as
desired.  The scheduler is stored on ``app.state.scheduler`` for
visibility and to facilitate graceful shutdown.
"""

from __future__ import annotations

from fastapi import FastAPI

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
except Exception:
    AsyncIOScheduler = None  # type: ignore


def maybe_start_scheduled_jobs(app: FastAPI) -> None:
    """Start the scheduler if APScheduler is available and not already running."""
    if AsyncIOScheduler is None:
        return
    if getattr(app.state, "scheduler", None) is not None:
        return

    scheduler = AsyncIOScheduler()
    # Example job: no-op placeholder
    # async def noop_job():
    #     return None
    # scheduler.add_job(noop_job, "interval", minutes=10)
    scheduler.start()
    app.state.scheduler = scheduler  # type: ignore[attr-defined]