"""Distributed tracing compatibility helpers."""

from __future__ import annotations

import contextlib
import functools
import inspect
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional tracing dependency
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
except ImportError:  # pragma: no cover
    class OTLPSpanExporter:  # type: ignore[too-many-ancestors]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._spans: list[dict[str, Any]] = []

        def create_span(self, name: str = "", **kwargs: Any) -> dict[str, Any]:
            span = {"name": name, **kwargs}
            self._spans.append(span)
            return span

    class _TracerProviderStub:
        def __init__(self) -> None:
            self._spans: list[str] = []

        def start_as_current_span(self, name: str, **_kwargs: Any):
            self._spans.append(name)
            return contextlib.nullcontext()

        def add_span_processor(self, _processor: Any) -> None:
            return None

    class _TraceAPIStub:
        def __init__(self) -> None:
            self._provider = _TracerProviderStub()

        def set_tracer_provider(self, provider: Any) -> None:
            self._provider = provider

        def get_tracer_provider(self) -> Any:
            return self._provider

    trace = _TraceAPIStub()  # type: ignore[assignment]
    TracerProvider = _TracerProviderStub  # type: ignore[assignment]

F = TypeVar("F", bound=Callable[..., Any])


def setup_tracing(*_args: Any, **_kwargs: Any) -> None:
    """Initialise tracing exporters and providers (minimal shim)."""
    exporter = OTLPSpanExporter()
    provider = TracerProvider()
    try:
        trace.set_tracer_provider(provider)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        logger.debug("Failed to set tracer provider", exc_info=True)

    # Legacy behaviour triggered exporter/provider side-effects for smoke tests.
    try:
        if hasattr(provider, "create_span"):
            provider.create_span("tracing-setup")
    except Exception:  # pragma: no cover
        logger.debug("Tracer provider span creation failed", exc_info=True)
    try:
        exporter.create_span("tracing-setup")
    except Exception:  # pragma: no cover
        logger.debug("Exporter span creation failed", exc_info=True)


def _span_context(name: str, attributes: dict[str, Any] | None):
    provider = trace.get_tracer_provider()  # type: ignore[attr-defined]
    start_span = getattr(provider, "start_as_current_span", None)
    if start_span is None:
        return contextlib.nullcontext()
    try:
        ctx = start_span(name, attributes=attributes or {})
    except TypeError:
        ctx = start_span(name)
    return ctx if ctx is not None else contextlib.nullcontext()


def traced(
    func: F | None = None,
    *,
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator attaching a span around sync and async callables."""

    def decorator(target: F) -> F:
        span_name = name or target.__name__

        if inspect.iscoroutinefunction(target):

            @functools.wraps(target)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                ctx = _span_context(span_name, attributes)
                if hasattr(ctx, "__aenter__"):
                    async with ctx:  # type: ignore[misc]
                        return await target(*args, **kwargs)
                with ctx:
                    return await target(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(target)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _span_context(span_name, attributes)
            with ctx:
                return target(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator


__all__ = ["setup_tracing", "traced", "OTLPSpanExporter", "TracerProvider", "trace"]
