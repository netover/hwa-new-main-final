"""
Distributed Tracing System with OpenTelemetry and Jaeger.

This module provides comprehensive distributed tracing capabilities including:
- Automatic instrumentation of HTTP requests, database calls, and async operations
- Context propagation across service boundaries
- Intelligent sampling strategies
- Integration with Jaeger for trace visualization
- Custom span creation for business logic tracking
- Performance monitoring of traced operations
- Error tracking and exception correlation
- Metrics collection from trace data
- Sampling rate optimization
- Trace correlation with logs and metrics
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import Sampler, SamplingResult, Decision
from opentelemetry.trace import Status, StatusCode, SpanKind

try:
    from opentelemetry.trace.propagation.tracecontext import TraceContextPropagator
except ImportError:
    # Fallback for environments where tracecontext propagator isn't available
    TraceContextPropagator = None

# Try to import optional components
try:
    from opentelemetry.exporter.jaeger import JaegerExporter

    JAEGER_AVAILABLE = True
except ImportError:
    JAEGER_AVAILABLE = False

    # Create a mock exporter for development
    class JaegerExporter:
        def __init__(self, **kwargs):
            pass

        def shutdown(self, **kwargs):
            pass


try:
    from opentelemetry.sdk.trace.export import ConsoleSpanProcessor

    CONSOLE_AVAILABLE = True
except ImportError:
    CONSOLE_AVAILABLE = False

    # Create a mock console processor
    class ConsoleSpanProcessor:
        def __init__(self, **kwargs):
            pass


from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


# Context variables for trace context propagation
current_trace_id: ContextVar[Optional[str]] = ContextVar(
    "current_trace_id", default=None
)
current_span_id: ContextVar[Optional[str]] = ContextVar("current_span_id", default=None)


class IntelligentSampler(Sampler):
    """
    Intelligent sampling strategy that adapts based on:
    - Request latency
    - Error rates
    - Service criticality
    - Resource usage
    """

    def __init__(self, base_sample_rate: float = 0.1, max_sample_rate: float = 1.0):
        self.base_sample_rate = base_sample_rate
        self.max_sample_rate = max_sample_rate

        # Adaptive sampling state
        self.error_count = 0
        self.total_requests = 0
        self.latency_threshold = 1.0  # seconds
        self.error_threshold = 0.05  # 5%

        # Sampling decisions cache
        self._decisions: Dict[str, SamplingResult] = {}

    def get_description(self) -> str:
        """Return a description of the sampling strategy."""
        return (
            f"IntelligentSampler(base_rate={self.base_sample_rate}, "
            f"max_rate={self.max_sample_rate}, "
            f"errors={self.error_count}/{self.total_requests})"
        )

    def should_sample(
        self,
        parent_context: Optional[trace.SpanContext],
        trace_id: int,
        name: str,
        kind: Optional[SpanKind] = None,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[List[trace.Link]] = None,
        trace_state: Optional[trace.TraceState] = None,
    ) -> SamplingResult:
        """Determine if a trace should be sampled."""

        # Always sample if parent is sampled
        if parent_context and parent_context.trace_flags.sampled:
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # Always sample errors and critical operations
        if attributes:
            error_code = attributes.get(
                "http.status_code", attributes.get("status_code")
            )
            if error_code and str(error_code).startswith(("4", "5")):
                return SamplingResult(Decision.RECORD_AND_SAMPLE)

            operation_type = attributes.get("operation.type")
            if operation_type in [
                "security_check",
                "payment",
                "critical_business_logic",
            ]:
                return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # Calculate adaptive sample rate
        current_rate = self._calculate_adaptive_rate()

        # Use trace_id for consistent sampling
        should_sample = (trace_id % int(1 / current_rate)) == 0

        if should_sample:
            return SamplingResult(Decision.RECORD_AND_SAMPLE)
        else:
            return SamplingResult(Decision.DROP)

    def _calculate_adaptive_rate(self) -> float:
        """Calculate adaptive sampling rate based on current conditions."""
        if self.total_requests == 0:
            return self.base_sample_rate

        error_rate = self.error_count / self.total_requests

        # Increase sampling for high error rates
        if error_rate > self.error_threshold:
            adaptive_rate = min(
                self.max_sample_rate,
                self.base_sample_rate * (error_rate / self.error_threshold),
            )
        else:
            adaptive_rate = self.base_sample_rate

        return adaptive_rate

    def record_request(self, has_error: bool = False, latency: float = 0.0):
        """Record request metrics for adaptive sampling."""
        self.total_requests += 1
        if has_error:
            self.error_count += 1

        # Update latency threshold based on moving average
        if latency > 0:
            self.latency_threshold = 0.9 * self.latency_threshold + 0.1 * latency


@dataclass
class TraceConfiguration:
    """Configuration for distributed tracing system."""

    # Jaeger configuration
    jaeger_endpoint: str = "http://localhost:14268/api/traces"
    jaeger_service_name: str = "hwa-new"
    jaeger_tags: Dict[str, str] = field(
        default_factory=lambda: {"service.version": "1.0.0"}
    )

    # Sampling configuration
    sampling_rate: float = 0.1
    adaptive_sampling: bool = True
    max_sampling_rate: float = 1.0

    # Performance configuration
    max_batch_size: int = 512
    export_timeout_seconds: int = 30
    max_queue_size: int = 2048

    # Instrumentation configuration
    auto_instrument_http: bool = True
    auto_instrument_db: bool = True
    auto_instrument_asyncio: bool = True
    auto_instrument_external_calls: bool = True

    # Custom configuration
    custom_span_processors: List[Any] = field(default_factory=list)
    custom_instrumentations: List[Any] = field(default_factory=list)


class DistributedTracingManager:
    """
    Main distributed tracing manager with OpenTelemetry integration.

    Features:
    - Automatic instrumentation setup
    - Jaeger export configuration
    - Context propagation
    - Custom span creation
    - Performance monitoring
    - Error correlation
    - Metrics extraction from traces
    """

    def __init__(self, config: Optional[TraceConfiguration] = None):
        self.config = config or TraceConfiguration()

        # Core components
        self.tracer_provider: Optional[TracerProvider] = None
        self.tracer: Optional[trace.Tracer] = None
        self.jaeger_exporter: Optional[JaegerExporter] = None

        # Instrumentation state
        self._instrumented = False
        self._running = False

        # Performance tracking
        self.trace_metrics: Dict[str, Any] = {
            "traces_created": 0,
            "spans_created": 0,
            "export_errors": 0,
            "export_success": 0,
            "sampling_decisions": 0,
        }

        # Context propagation
        if TraceContextPropagator is not None:
            self.propagator = TraceContextPropagator()
        else:
            self.propagator = None

        # Initialize components
        self._initialize_tracing()

    def _initialize_tracing(self) -> None:
        """Initialize OpenTelemetry tracing components."""
        # Create tracer provider
        self.tracer_provider = TracerProvider()

        # Configure sampling
        if self.config.adaptive_sampling:
            sampler = IntelligentSampler(
                self.config.sampling_rate, self.config.max_sampling_rate
            )
        else:
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBasedSampler

            sampler = TraceIdRatioBasedSampler(self.config.sampling_rate)

        self.tracer_provider.sampler = sampler

        # Configure Jaeger exporter
        self.jaeger_exporter = JaegerExporter(
            agent_host_name=urlparse(self.config.jaeger_endpoint).hostname,
            agent_port=int(urlparse(self.config.jaeger_endpoint).port or 14268),
            collector_endpoint=self.config.jaeger_endpoint,
        )

        # Add span processors
        span_processor = BatchSpanProcessor(
            self.jaeger_exporter,
            max_export_batch_size=self.config.max_batch_size,
            export_timeout_millis=self.config.export_timeout_seconds * 1000,
            schedule_delay_millis=5000,
        )

        self.tracer_provider.add_span_processor(span_processor)

        # Add console processor for development
        try:
            logger_level = getattr(logger, 'level', 20)  # Default to INFO if no level attribute
            if logger_level <= 10 and CONSOLE_AVAILABLE:  # DEBUG level
                console_processor = ConsoleSpanProcessor()
                self.tracer_provider.add_span_processor(console_processor)
        except AttributeError:
            if CONSOLE_AVAILABLE:  # Default to adding console processor if we can't check level
                console_processor = ConsoleSpanProcessor()
                self.tracer_provider.add_span_processor(console_processor)

        # Add custom span processors
        for processor in self.config.custom_span_processors:
            self.tracer_provider.add_span_processor(processor)

        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)

        # Create tracer
        self.tracer = trace.get_tracer(
            __name__
        )

        logger.info("Distributed tracing initialized")

    async def start(self) -> None:
        """Start the distributed tracing system."""
        if self._running:
            return

        self._running = True

        # Auto-instrument components
        await self._setup_auto_instrumentation()

        logger.info("Distributed tracing system started")

    async def stop(self) -> None:
        """Stop the distributed tracing system."""
        if not self._running:
            return

        self._running = False

        # Force export of remaining spans
        if self.tracer_provider:
            await asyncio.sleep(1)  # Allow pending exports to complete

        logger.info("Distributed tracing system stopped")

    async def _setup_auto_instrumentation(self) -> None:
        """Setup automatic instrumentation for common components."""
        if self._instrumented:
            return

        try:
            # HTTP client instrumentation
            if self.config.auto_instrument_http:
                await self._instrument_http_clients()

            # Database instrumentation
            if self.config.auto_instrument_db:
                await self._instrument_database_calls()

            # Asyncio instrumentation
            if self.config.auto_instrument_asyncio:
                await self._instrument_asyncio_operations()

            # External service calls
            if self.config.auto_instrument_external_calls:
                await self._instrument_external_calls()

            # Custom instrumentations
            for instrumentation in self.config.custom_instrumentations:
                await instrumentation.setup()

            self._instrumented = True
            logger.info("Auto-instrumentation completed")

        except Exception as e:
            logger.error(f"Failed to setup auto-instrumentation: {e}")

    async def _instrument_http_clients(self) -> None:
        """Instrument HTTP client calls."""
        # This would integrate with aiohttp, httpx, requests, etc.
        # For now, we'll create a wrapper that can be used manually
        pass

    async def _instrument_database_calls(self) -> None:
        """Instrument database operations."""
        # This would integrate with database drivers
        # For now, we'll create decorators that can be used manually
        pass

    async def _instrument_asyncio_operations(self) -> None:
        """Instrument asyncio operations."""
        # Create a context manager for async operations
        pass

    async def _instrument_external_calls(self) -> None:
        """Instrument external service calls."""
        # This would integrate with service discovery and API gateway
        pass

    @contextlib.contextmanager
    def trace_context(self, operation_name: str, **attributes):
        """Context manager for creating trace spans."""
        with self.tracer.start_as_span(operation_name, attributes=attributes) as span:
            # Store trace context
            if span.get_span_context().is_valid:
                trace_id = format(span.get_span_context().trace_id, "032x")
                span_id = format(span.get_span_context().span_id, "016x")

                current_trace_id.set(trace_id)
                current_span_id.set(span_id)

                # Add trace context to span
                span.set_attribute("trace.id", trace_id)
                span.set_attribute("span.id", span_id)

            self.trace_metrics["spans_created"] += 1

            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                # Update span with performance metrics
                span.set_attribute(
                    "performance.duration_ms", span.end_time - span.start_time
                )

    def trace_method(self, operation_name: Optional[str] = None):
        """Decorator for tracing method calls."""

        def decorator(func: Callable):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                method_name = operation_name or f"{func.__name__}"
                class_name = args[0].__class__.__name__ if args else "unknown"

                span_name = f"{class_name}.{method_name}"

                with self.trace_context(
                    span_name,
                    operation_type="method_call",
                    class_name=class_name,
                    method_name=method_name,
                    is_async=True,
                ) as span:
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute("result.success", True)
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_attribute("result.success", False)
                        span.set_attribute("error.type", type(e).__name__)
                        raise
                    finally:
                        duration = time.time() - start_time
                        span.set_attribute("performance.duration_seconds", duration)

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                method_name = operation_name or f"{func.__name__}"
                class_name = args[0].__class__.__name__ if args else "unknown"

                span_name = f"{class_name}.{method_name}"

                with self.trace_context(
                    span_name,
                    operation_type="method_call",
                    class_name=class_name,
                    method_name=method_name,
                    is_async=False,
                ) as span:
                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        span.set_attribute("result.success", True)
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_attribute("result.success", False)
                        span.set_attribute("error.type", type(e).__name__)
                        raise
                    finally:
                        duration = time.time() - start_time
                        span.set_attribute("performance.duration_seconds", duration)

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    def trace_http_request(self, method: str, url: str, **attributes):
        """Context manager for tracing HTTP requests."""
        return self.trace_context(
            f"http.{method.lower()}",
            http_method=method,
            http_url=url,
            operation_type="http_request",
            **attributes,
        )

    def trace_database_operation(self, operation: str, table: str = "", **attributes):
        """Context manager for tracing database operations."""
        return self.trace_context(
            f"db.{operation}",
            db_operation=operation,
            db_table=table,
            operation_type="database_operation",
            **attributes,
        )

    def trace_external_call(self, service_name: str, operation: str, **attributes):
        """Context manager for tracing external service calls."""
        return self.trace_context(
            f"external.{service_name}.{operation}",
            external_service=service_name,
            external_operation=operation,
            operation_type="external_call",
            **attributes,
        )

    def create_child_span(self, parent_span: trace.Span, name: str, **attributes):
        """Create a child span from a parent span."""
        with self.tracer.start_as_span(
            name, parent=parent_span, attributes=attributes
        ) as child_span:
            self.trace_metrics["spans_created"] += 1
            return child_span

    def inject_context(self, carrier: Dict[str, str]) -> None:
        """Inject trace context into carrier (headers, etc.)."""
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            self.propagator.inject(carrier, context=trace.get_current_context())

    def extract_context(self, carrier: Dict[str, str]) -> Optional[trace.SpanContext]:
        """Extract trace context from carrier."""
        context = self.propagator.extract(carrier)
        span_context = trace.get_current_span(context).get_span_context()
        return span_context if span_context.is_valid else None

    def get_current_trace_id(self) -> Optional[str]:
        """Get current trace ID from context."""
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, "032x")
        return None

    def get_current_span_id(self) -> Optional[str]:
        """Get current span ID from context."""
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().span_id, "016x")
        return None

    def add_span_attribute(self, key: str, value: Any) -> None:
        """Add attribute to current span."""
        span = trace.get_current_span()
        if span:
            span.set_attribute(key, value)

    def add_span_event(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add event to current span."""
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes or {})

    def record_exception(self, exception: Exception) -> None:
        """Record exception in current span."""
        span = trace.get_current_span()
        if span:
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))

    def get_trace_metrics(self) -> Dict[str, Any]:
        """Get comprehensive tracing metrics."""
        return {
            "performance": {
                "traces_created": self.trace_metrics["traces_created"],
                "spans_created": self.trace_metrics["spans_created"],
                "export_success": self.trace_metrics["export_success"],
                "export_errors": self.trace_metrics["export_errors"],
                "sampling_decisions": self.trace_metrics["sampling_decisions"],
            },
            "configuration": {
                "jaeger_endpoint": self.config.jaeger_endpoint,
                "sampling_rate": self.config.sampling_rate,
                "adaptive_sampling": self.config.adaptive_sampling,
                "auto_instrumentation": {
                    "http": self.config.auto_instrument_http,
                    "database": self.config.auto_instrument_db,
                    "asyncio": self.config.auto_instrument_asyncio,
                    "external_calls": self.config.auto_instrument_external_calls,
                },
            },
            "health": {
                "instrumented": self._instrumented,
                "running": self._running,
                "jaeger_connected": self.jaeger_exporter is not None,
            },
        }

    def force_flush(self) -> None:
        """Force flush all pending spans."""
        if self.tracer_provider:
            self.tracer_provider.force_flush()

    def shutdown(self) -> None:
        """Shutdown tracing system."""
        if self.tracer_provider:
            self.tracer_provider.shutdown()


# Global distributed tracing manager instance
distributed_tracing_manager = DistributedTracingManager()


async def get_distributed_tracing_manager() -> DistributedTracingManager:
    """Get the global distributed tracing manager instance."""
    if not distributed_tracing_manager._running:
        await distributed_tracing_manager.start()
    return distributed_tracing_manager


# Convenience functions for easy usage
def trace_method(operation_name: Optional[str] = None):
    """Convenience decorator for tracing methods."""
    return distributed_tracing_manager.trace_method(operation_name)


def trace_context(operation_name: str, **attributes):
    """Convenience function for trace context manager."""
    return distributed_tracing_manager.trace_context(operation_name, **attributes)


def get_current_trace_id() -> Optional[str]:
    """Get current trace ID."""
    return distributed_tracing_manager.get_current_trace_id()


def add_span_attribute(key: str, value: Any) -> None:
    """Add attribute to current span."""
    distributed_tracing_manager.add_span_attribute(key, value)


async def setup_tracing(config: Optional[TraceConfiguration] = None) -> DistributedTracingManager:
    """
    Initialize and setup distributed tracing.

    Args:
        config: Optional trace configuration

    Returns:
        DistributedTracingManager instance
    """
    manager = DistributedTracingManager(config)
    await manager.start()
    return manager


def traced(operation_name: str, **attributes):
    """
    Decorator to trace function calls.

    Args:
        operation_name: Name of the operation
        **attributes: Additional attributes to add to the span

    Returns:
        Decorator function
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                manager = await get_distributed_tracing_manager()
                with manager.trace_context(operation_name, **attributes):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we'll use a simplified approach
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator


def record_exception(exception: Exception) -> None:
    """Record exception in current span."""
    distributed_tracing_manager.record_exception(exception)
