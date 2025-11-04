"""Middleware responsible for collecting simple HTTP metrics."""

from __future__ import annotations

import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect request counts, error counts and latency aggregates."""

    def __init__(self, app: ASGIApp, state_key: str = "metrics") -> None:
        super().__init__(app)
        self.state_key = state_key

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        metrics: dict[str, Any] | None = getattr(
            request.app.state, self.state_key, None
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        except Exception:
            if metrics is not None:
                metrics["http_request_errors"] = (
                    metrics.get("http_request_errors", 0) + 1
                )
            raise
        finally:
            if metrics is not None:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                metrics["http_request_count"] = (
                    metrics.get("http_request_count", 0) + 1
                )
                metrics["http_request_latency_sum_ms"] = (
                    metrics.get("http_request_latency_sum_ms", 0.0) + elapsed_ms
                )
