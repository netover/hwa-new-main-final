"""Minimal IdempotencyManager stub.

Many parts of the Resync API reference an ``IdempotencyManager`` to
coordinate idempotent operations, typically backed by Redis or another
central store.  In the absence of the full implementation, this stub
provides the required methods but does not enforce idempotency.  All
operations are effectively no-ops or return defaults, which allows
dependent modules to function without modification.

Developers wishing to implement proper idempotent request handling
can extend this class with persistent storage and deduplication logic.
"""

from __future__ import annotations

from typing import Any, Optional


class IdempotencyManager:
    """No-op idempotency manager.

    This stub emulates the interface of the full idempotency manager
    without storing any state.  All operations succeed immediately
    and assume that each request is unique.
    """

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        # A real implementation would store a redis client or other
        # persistence layer.  We ignore it here.
        self._redis = redis_client

    async def initialize(self, redis_client: Optional[Any] = None) -> None:
        """Initialize the manager with a Redis client.

        This method is kept for compatibility; it does nothing in this
        simplified implementation.
        """
        self._redis = redis_client

    async def get_or_create_key(self, key: str) -> str:
        """Return a canonical idempotency key.

        In a real implementation this would generate or validate a
        unique key to identify a request.  Here we simply return the
        provided key.
        """
        return key

    async def is_duplicate(self, key: str) -> bool:
        """Check whether a given key has been seen before.

        Always returns ``False`` in this stub, indicating the request
        should be processed as unique.
        """
        return False

    async def record(self, key: str, response: Any) -> None:
        """Record the response for a given idempotency key.

        In the real implementation this would persist the response so
        it can be returned for subsequent duplicate requests.  Here it
        simply returns immediately.
        """
        return None

    async def get_record(self, key: str) -> Optional[Any]:
        """Retrieve a recorded response.

        Always returns ``None`` in this stub since responses are not
        actually persisted.
        """
        return None



