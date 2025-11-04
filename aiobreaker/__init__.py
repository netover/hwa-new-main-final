from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Callable, Iterable, List


class CircuitBreaker:
    """Minimal async circuit breaker used in tests."""

    def __init__(
        self,
        *,
        fail_max: int = 5,
        timeout_duration: timedelta = timedelta(seconds=60),
        exclude: Iterable[type[BaseException]] | None = None,
        name: str | None = None,
        listeners: Iterable[Callable[..., Any]] | None = None,
    ) -> None:
        self.fail_max = fail_max
        self.timeout_duration = timeout_duration
        self.exclude = list(exclude or [])
        self.name = name or "breaker"
        self._listeners: List[Callable[..., Any]] = list(listeners or [])
        self._consecutive_failures = 0
        self._state = "closed"
        self._last_failure: float | None = None
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
        }

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._metrics["total_calls"] += 1
        if asyncio.iscoroutinefunction(func):
            coro = func(*args, **kwargs)
        else:
            async def coro_wrapper():
                return func(*args, **kwargs)

            coro = coro_wrapper()
        try:
            result = await coro
            self._metrics["successful_calls"] += 1
            self._consecutive_failures = 0
            return result
        except Exception as exc:
            self._metrics["failed_calls"] += 1
            self._consecutive_failures += 1
            self._last_failure = asyncio.get_event_loop().time()
            raise

    def get_metrics(self) -> dict[str, Any]:
        total = self._metrics["total_calls"]
        success = self._metrics["successful_calls"]
        return {
            **self._metrics,
            "success_rate": success / total if total else 0,
            "consecutive_failures": self._consecutive_failures,
        }


__all__ = ["CircuitBreaker"]
