"""Exception definitions for the :mod:`slowapi` test stub.

The test suite raises and inspects :class:`RateLimitExceeded` to
signal when a client has exceeded their allowed request quota. This
exception exposes attributes describing the limit and the window and
optionally a retry delay. The real ``slowapi`` library provides a
similar exception; here we supply a minimal compatible version.
"""

from __future__ import annotations

from typing import Any


class RateLimitExceeded(Exception):
    """Exception raised when a rate limit is exceeded.

    Parameters
    ----------
    detail:
        Optional human‑readable message describing the error.
    limit:
        The maximum number of requests permitted during the window.
    window:
        The size of the time window in seconds.
    retry_after:
        The number of seconds the client should wait before retrying.
    """

    def __init__(
        self,
        detail: str | None = None,
        *,
        limit: int | None = None,
        window: int | None = None,
        retry_after: int | None = None,
        **_: Any,
    ) -> None:
        super().__init__(detail or "Rate limit exceeded")
        self.limit: int | None = limit
        self.window: int | None = window
        self.retry_after: int | None = retry_after
        self.detail: str = detail or "Rate limit exceeded"

    def __repr__(self) -> str:  # pragma: no cover - representation is not tested
        return (
            f"RateLimitExceeded(limit={self.limit}, window={self.window}, "
            f"retry_after={self.retry_after}, detail={self.detail!r})"
        )


__all__ = ["RateLimitExceeded"]