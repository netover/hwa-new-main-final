"""Asynchronous task manager compatibility shim.

The original implementation provided advanced scheduling, monitoring and
instrumentation.  For the purposes of the refactor we only need a lightweight
API that keeps the public surface area used throughout the codebase and in the
test-suite.  This module offers a small wrapper around ``asyncio`` primitives
that mimics the legacy behaviour closely enough for unit tests.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable, Iterable, Optional


async def _invoke_callable(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Execute ``func`` supporting sync, async and coroutine-returning callables."""
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result  # type: ignore[return-value]
    return result


class ManagedTask(asyncio.Future):
    """Asyncio future with metadata used by the legacy TaskManager."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        func: Callable[..., Any],
        args: Iterable[Any],
        kwargs: dict[str, Any],
        *,
        name: str | None = None,
    ) -> None:
        super().__init__()
        self.name = name or f"task-{id(self)}"
        self._managed_loop = loop
        self._runner: Optional[asyncio.Task[Any]] = None
        self._start_runner(func, args, kwargs)

    # ------------------------------------------------------------------
    def _start_runner(
        self,
        func: Callable[..., Any],
        args: Iterable[Any],
        kwargs: dict[str, Any],
    ) -> None:
        async def runner() -> None:
            try:
                result = await _invoke_callable(func, *args, **kwargs)
                if not self.done():
                    super().set_result(result)
            except Exception as exc:  # pragma: no cover - defensive
                if not self.done():
                    super().set_exception(exc)

        self._runner = self._managed_loop.create_task(runner())

    # ------------------------------------------------------------------
    def cancel(self) -> bool:  # noqa: D401 - short doc inherited from Future
        """Cancel the managed task and the underlying runner."""
        if self._runner and not self._runner.done():
            self._runner.cancel()
        return super().cancel()

    def set_result(self, result: Any) -> None:  # pragma: no cover - passthrough
        """Expose ``set_result`` publicly for compatibility with legacy tests."""
        super().set_result(result)

    def set_exception(self, exception: BaseException) -> None:  # pragma: no cover
        """Expose ``set_exception`` publicly for compatibility."""
        super().set_exception(exception)


class TaskManager:
    """Thin wrapper responsible for bookkeeping asyncio tasks."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._active_tasks: set[ManagedTask] = set()
        self._total_created = 0

    # ------------------------------------------------------------------
    def create_task(
        self,
        func: Callable[..., Any] | Awaitable[Any],
        *,
        name: str | None = None,
        args: Iterable[Any] | None = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> ManagedTask:
        """Create and track a managed task.

        The callable ``func`` can be synchronous or asynchronous.  Optional
        positional and keyword arguments can be supplied via ``args``/``kwargs``.
        """
        args = list(args or [])
        kwargs = dict(kwargs or {})

        if inspect.isawaitable(func):
            async def runner() -> Any:
                return await func  # type: ignore[return-value]

            actual_callable: Callable[..., Any] = runner
            args = []
            kwargs = {}
        else:
            actual_callable = func  # type: ignore[assignment]

        loop = self._loop or self._resolve_loop()
        managed = ManagedTask(
            loop=loop,
            func=actual_callable,
            args=args,
            kwargs=kwargs,
            name=name,
        )

        self._active_tasks.add(managed)
        self._total_created += 1
        managed.add_done_callback(self._active_tasks.discard)
        return managed

    # ------------------------------------------------------------------
    def _resolve_loop(self) -> asyncio.AbstractEventLoop:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            loop = self._loop
        return loop

    # ------------------------------------------------------------------
    def get_metrics(self) -> dict[str, int]:
        """Expose simple bookkeeping metrics used by the tests."""
        return {
            "total_tasks": self._total_created,
            "active_tasks": sum(1 for task in self._active_tasks if not task.done()),
        }


__all__ = ["TaskManager", "ManagedTask"]
