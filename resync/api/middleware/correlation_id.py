"""
Correlation ID ASGI middleware.

This middleware ensures that every HTTP request and response includes a
unique correlation identifier.  The correlation ID is propagated via
the ``X-Correlation-ID`` header.  If the client sends a valid
``X-Correlation-ID`` header it is reused; otherwise a UUID4 is
generated.  The correlation ID is stored in the request state and
added to the response headers.  WebSocket connections are ignored.

Example usage::

    from fastapi import FastAPI
    from resync.api.middleware.correlation_id import CorrelationIdMiddleware
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

This implementation does not record latency or increment metrics.
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable, Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_ID_HEADER = "X-Correlation-ID"
CORRELATION_ID_STATE_KEY = "correlation_id"


def _safe_cid(value: Optional[str]) -> str:
    """Validate or generate a correlation ID.

    If ``value`` is a valid UUID string it is returned as-is.  Otherwise
    a new UUID4 is generated and returned.  When ``value`` is ``None`` a
    new UUID4 is also generated.
    """
    if value:
        try:
            uuid.UUID(value)
            return value
        except Exception:
            pass
    return str(uuid.uuid4())


class CorrelationIdMiddleware:
    """ASGI middleware to propagate correlation IDs on HTTP requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only handle HTTP connections; pass through others
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Extract incoming correlation ID from headers (case-insensitive)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        cid = _safe_cid(headers.get("x-correlation-id"))

        # Store on request state for downstream handlers
        scope.setdefault("state", {})[CORRELATION_ID_STATE_KEY] = cid

        # Wrap send to inject the header into the response
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Append the correlation ID to response headers
                raw_headers = list(message.get("headers", []))
                raw_headers.append((CORRELATION_ID_HEADER.lower().encode(), cid.encode()))
                message["headers"] = raw_headers
            await send(message)

        # Call downstream app
        await self.app(scope, receive, send_wrapper)


def get_correlation_id_from_request(request: Any) -> Optional[str]:
    """Retrieve correlation ID from request state or headers."""
    cid = getattr(getattr(request, "state", None), CORRELATION_ID_STATE_KEY, None)
    if cid:
        return cid
    headers = getattr(request, "headers", {})
    return headers.get(CORRELATION_ID_HEADER)


__all__ = [
    "CORRELATION_ID_HEADER",
    "CORRELATION_ID_STATE_KEY",
    "CorrelationIdMiddleware",
    "get_correlation_id_from_request",
]
