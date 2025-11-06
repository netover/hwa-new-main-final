"""Helpers to initialise FastAPI application state objects."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Iterable, Set

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _default_metrics() -> dict[str, Any]:
    return {
        "http_request_count": 0,
        "http_request_errors": 0,
        "http_request_latency_sum_ms": 0.0,
        "ws_connection_count": 0,
        "ws_message_count": 0,
    }


def initialize_state(app: FastAPI) -> None:
    """Populate ``app.state`` with shared objects used across the app."""
    if getattr(app.state, "metrics", None) is None:
        app.state.metrics = _default_metrics()  # type: ignore[attr-defined]

    if getattr(app.state, "background_tasks", None) is None:
        app.state.background_tasks = set()  # type: ignore[attr-defined]

    if getattr(app.state, "_tws_config", None) is None:
        app.state._tws_config = {  # type: ignore[attr-defined]
            "host": None,
            "port": None,
            "user": None,
            "password": None,
            "verify_tls": False,
            "mock_mode": True,
        }

    if getattr(app.state, "incidents", None) is None:
        app.state.incidents = []  # type: ignore[attr-defined]

    if getattr(app.state, "sla_risk_scores", None) is None:
        app.state.sla_risk_scores = {}  # type: ignore[attr-defined]

    def register_background_task(coro: Awaitable[Any], *, name: str) -> asyncio.Task[Any]:  # type: ignore
        tasks: Set[asyncio.Task[Any]] = getattr(app.state, "background_tasks")  # type: ignore
        task = asyncio.create_task(coro, name=name)  # type: ignore[arg-type]
        tasks.add(task)  # type: ignore

        def _cleanup(completed: asyncio.Task[Any]) -> None:  # type: ignore
            tasks.discard(completed)
            if completed.cancelled():
                return
            try:
                exception = completed.exception()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Unable to retrieve exception for task %s: %s", name, exc)
                return
            if exception:
                logger.exception("Background task %s failed", name, exc_info=exception)

        task.add_done_callback(_cleanup)  # type: ignore
        return task  # type: ignore

    app.state.register_background_task = register_background_task  # type: ignore[attr-defined]

    async def _cancel_background_tasks() -> None:
        tasks: Iterable[asyncio.Task[Any]] = list(
            getattr(app.state, "background_tasks", [])
        )
        if not tasks:
            return
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app.add_event_handler("shutdown", _cancel_background_tasks)  # type: ignore
