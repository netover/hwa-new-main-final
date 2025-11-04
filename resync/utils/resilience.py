"""Resilience helpers (circuit breaker, retry, timeout) for legacy code."""

from __future__ import annotations

import asyncio
import random
import time
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def circuit_breaker(**_kwargs) -> Callable[[F], F]:
    """No-op circuit breaker decorator kept for compatibility."""

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = False,
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff (async/sync)."""

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                retries = kwargs.pop("max_retries", max_retries)
                delay = kwargs.pop("initial_backoff", base_delay)
                attempt = 0
                while True:
                    try:
                        return await func(*args, **kwargs)
                    except Exception:
                        if attempt >= retries:
                            raise
                        sleep_for = min(delay, max_delay)
                        if jitter:
                            sleep_for = random.uniform(0, sleep_for)
                        await asyncio.sleep(sleep_for)
                        delay = min(delay * 2, max_delay)
                        attempt += 1

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = kwargs.pop("max_retries", max_retries)
            delay = kwargs.pop("initial_backoff", base_delay)
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt >= retries:
                        raise
                    sleep_for = min(delay, max_delay)
                    if jitter:
                        sleep_for = random.uniform(0, sleep_for)
                    time.sleep(sleep_for)
                    delay = min(delay * 2, max_delay)
                    attempt += 1

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def with_timeout(timeout: float) -> Callable[[F], F]:
    """Timeout decorator wrapping asyncio coroutines."""

    def decorator(func: F) -> F:
        if not asyncio.iscoroutinefunction(func):
            return func

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["circuit_breaker", "retry_with_backoff", "with_timeout"]
