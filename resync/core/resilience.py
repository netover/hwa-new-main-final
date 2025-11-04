"""Async resilience helpers used across the codebase."""

from __future__ import annotations

import asyncio
import inspect
import time
import builtins
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple, Type

from resync.utils.retry_utils import retry_with_backoff_async


class CircuitBreakerError(RuntimeError):
    """Raised when a circuit breaker is open and rejects calls."""


@dataclass(slots=True)
class CircuitBreakerConfig:
    """Configuration used to build circuit breakers."""

    name: str
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    exclude: Tuple[Type[BaseException], ...] = tuple()


class CircuitBreaker:
    """Small asynchronous circuit breaker implementation."""

    def __init__(self, config: CircuitBreakerConfig) -> None:
        self.config = config
        self._fail_max = max(1, config.failure_threshold)
        self._timeout = max(1, config.recovery_timeout)
        self._exclude = tuple(config.exclude)

        self._state = "closed"
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None
        self._metrics: Dict[str, int] = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
        }
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    async def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a callable while observing breaker state."""
        async with self._lock:
            if self._state == "open":
                if self._opened_at is not None and self._cooldown_elapsed():
                    self._state = "half_open"
                else:
                    raise CircuitBreakerError(self.config.name)

        self._metrics["total_calls"] += 1
        try:
            result = await self._invoke(func, *args, **kwargs)
        except Exception as exc:
            if not isinstance(exc, self._exclude):
                self._record_failure()
            raise
        else:
            self._record_success()
            return result

    # ------------------------------------------------------------------ #
    async def _invoke(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result  # type: ignore[return-value]
        return result

    def _record_failure(self) -> None:
        self._metrics["failed_calls"] += 1
        self._consecutive_failures += 1
        self._opened_at = time.monotonic()

        if self._state == "half_open" or self._consecutive_failures >= self._fail_max:
            self._state = "open"
        else:
            self._state = "half_open"

    def _record_success(self) -> None:
        self._metrics["successful_calls"] += 1
        self._consecutive_failures = 0
        self._state = "closed"
        self._opened_at = None

    def _cooldown_elapsed(self) -> bool:
        if self._opened_at is None:
            return True
        return (time.monotonic() - self._opened_at) >= self._timeout

    # ------------------------------------------------------------------ #
    @property
    def state(self) -> str:
        return self._state

    def reset(self) -> None:
        self._state = "closed"
        self._consecutive_failures = 0
        self._opened_at = None

    def get_metrics(self) -> Dict[str, Any]:
        total = self._metrics["total_calls"]
        success = self._metrics["successful_calls"]
        return {
            **self._metrics,
            "success_rate": success / total if total else 0.0,
            "consecutive_failures": self._consecutive_failures,
        }


class CircuitBreakerManager:
    """Registry maintaining named circuit breakers."""

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}

    def register(
        self,
        name: str,
        *,
        fail_max: int = 5,
        reset_timeout: int = 60,
        exclude: Iterable[Type[BaseException]] | None = None,
    ) -> CircuitBreaker:
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=fail_max,
            recovery_timeout=reset_timeout,
            exclude=tuple(exclude or ()),
        )
        breaker = CircuitBreaker(config)
        self._breakers[name] = breaker
        return breaker

    def get_or_create(self, config: CircuitBreakerConfig) -> CircuitBreaker:
        breaker = self._breakers.get(config.name)
        if breaker is None:
            breaker = CircuitBreaker(config)
            self._breakers[config.name] = breaker
        return breaker

    async def call(self, name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        breaker = self._breakers.get(name)
        if breaker is None:
            breaker = self.register(name)
        return await breaker.call(func, *args, **kwargs)

    def state(self, name: str) -> str:
        breaker = self._breakers.get(name)
        return breaker.state if breaker else "closed"

    def reset(self, name: str) -> None:
        breaker = self._breakers.get(name)
        if breaker:
            breaker.reset()

    def __getitem__(self, name: str) -> CircuitBreaker:
        return self._breakers[name]


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerManager",
    "retry_with_backoff_async",
]

if not hasattr(builtins, "retry_with_backoff_async"):
    setattr(builtins, "retry_with_backoff_async", retry_with_backoff_async)
