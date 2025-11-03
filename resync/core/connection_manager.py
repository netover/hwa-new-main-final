"""Minimal connection manager for WebSocket handling.

The full project defined a comprehensive connection manager responsible for
tracking active WebSocket connections, broadcasting messages, and routing
communication to individual clients.  For the simplified version of the
project, this module provides a bare-bones implementation that stores
active connections but does not enforce any protocol-level policies.

This stub allows the rest of the application to import
``ConnectionManager`` without encountering a missing module error.  It
can be extended with real functionality as needed.
"""

from __future__ import annotations

from typing import Any, List

try:
    from fastapi.websockets import WebSocket
except ImportError:  # pragma: no cover
    # Define a minimal WebSocket type hint when FastAPI is unavailable.
    WebSocket = Any  # type: ignore


class ConnectionManager:
    """Tracks active WebSocket connections.

    This manager maintains a list of active connections and exposes
    coroutines for connecting, disconnecting, sending personal messages,
    and broadcasting to all connected clients.  The methods are
    implemented as no-ops in this stub.
    """

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Register a new WebSocket connection."""
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a message to a single WebSocket connection.

        In this stub, no actual sending is performed.  In a full
        implementation, you would call ``await websocket.send_text``.
        """
        # Suppress unused variable warnings
        _ = (message, websocket)

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected WebSocket clients.

        This stub does not perform any broadcasting.  Extend this method
        to iterate over ``self.active_connections`` and send the message.
        """
        _ = message



