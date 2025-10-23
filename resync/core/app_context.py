from __future__ import annotations

import uuid


class AppContext:
    """Application context for correlation ID management."""

    _current_correlation_id: str | None = None

    @classmethod
    def get_correlation_id(cls) -> str:
        """Get current correlation ID or generate a new one."""
        if cls._current_correlation_id is None:
            cls._current_correlation_id = generate_correlation_id()
        return cls._current_correlation_id

    @classmethod
    def set_correlation_id(cls, correlation_id: str) -> None:
        """Set correlation ID for current context."""
        cls._current_correlation_id = correlation_id

    @classmethod
    def reset_correlation_id(cls) -> None:
        """Reset correlation ID."""
        cls._current_correlation_id = None


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())
