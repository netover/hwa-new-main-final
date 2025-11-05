"""Minimal stub implementation of the ``slowapi`` package for testing.

This project relies on rate limiting functionality provided by the
``slowapi`` library. However, in the test environment we avoid
installing external dependencies. To allow the test suite to import
``slowapi`` symbols without error, we provide a small shim
implementing only what the tests require. Should additional
functionality be needed in the future, this stub can be extended.

The primary class exposed by the real library is :class:`Limiter`,
which acts as a decorator factory. Our implementation records the
rate limit string passed into the decorator and attaches it to the
wrapped function as a ``_rate_limit`` attribute. No real rate
limiting is enforced.

The :mod:`slowapi.errors` submodule defines the
:class:`RateLimitExceeded` exception. Tests expect this exception to
expose ``limit``, ``window`` and ``retry_after`` attributes. Our
version simply stores these attributes on the instance.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable, Awaitable, TypeVar

from .errors import RateLimitExceeded  # re-export for convenience

F = TypeVar("F", bound=Callable[..., Any])


class Limiter:
    """Light‑weight stand‑in for :class:`slowapi.Limiter`.

    The real ``slowapi`` library uses this class to enforce rate
    limiting policies on callables. Our version accepts the same
    constructor parameters for API compatibility but ignores them.
    Decorators returned by :meth:`limit` simply annotate the wrapped
    function with the supplied limit string via a ``_rate_limit``
    attribute. Both synchronous and asynchronous functions are
    supported; the wrapper calls the underlying function without
    imposing any limits.
    """

    def __init__(
        self,
        key_func: Callable[[Any], str] | None = None,
        default_limits: Iterable[str] | None = None,
        storage_uri: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.key_func = key_func
        self.default_limits = list(default_limits or [])
        self.storage_uri = storage_uri

    def limit(
        self,
        limit_value: str,
        *,
        key_func: Callable[[Any], str] | None = None,
    ) -> Callable[[F], F]:
        """Return a decorator storing ``limit_value`` on the wrapper.

        Parameters
        ----------
        limit_value:
            A string describing the rate limit (e.g. ``"100/minute"``).
        key_func:
            An optional function used by the real library to derive a
            unique identifier per request. It is accepted here for
            compatibility but is ignored.
        """

        def decorator(func: F) -> F:
            # Determine if the target is a coroutine function. Use the
            # presence of the coroutine flag (0x80) on the code object
            # instead of importing ``asyncio.iscoroutinefunction`` to
            # avoid unnecessary overhead. Both sync and async targets
            # must be handled separately so that the wrapper returns
            # synchronously when appropriate.
            if func.__code__.co_flags & 0x80:
                @wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return await func(*args, **kwargs)

                wrapper = async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return func(*args, **kwargs)

                wrapper = sync_wrapper  # type: ignore[assignment]

            # Attach metadata used by tests to inspect rate limits.
            setattr(wrapper, "_rate_limit", limit_value)
            return wrapper  # type: ignore[return-value]

        return decorator


__all__ = ["Limiter", "RateLimitExceeded"]