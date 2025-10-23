"""
Runtime telemetry and metrics system for Resync components.
Provides comprehensive monitoring, correlation IDs, and audit trails.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricCounter:
    """Thread-safe counter for metrics. Uses threading.Lock for performance since operations are very fast."""

    value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def increment(self, amount: int = 1) -> None:
        with self._lock:
            self.value += amount

    def get_and_reset(self) -> int:
        with self._lock:
            value = self.value
            self.value = 0
            return value

    def set(self, value: int) -> None:
        """Set the counter value."""
        with self._lock:
            self.value = value


@dataclass
class MetricGauge:
    """Thread-safe gauge for current values. Uses threading.Lock for performance since operations are very fast."""

    value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float) -> None:
        with self._lock:
            self.value = value

    def get(self) -> float:
        with self._lock:
            return self.value


@dataclass
class MetricHistogram:
    """Simple histogram for tracking distributions. Uses threading.Lock for performance since operations are very fast."""

    buckets: Dict[str, int] = field(default_factory=dict)
    samples: List[float] = field(default_factory=list)
    max_samples: int = 1000
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float) -> None:
        with self._lock:
            self.samples.append(value)
            if len(self.samples) > self.max_samples:
                self.samples.pop(0)


class RuntimeMetrics:
    """
    Comprehensive runtime telemetry system.
    Thread-safe and async-safe metrics collection.
    """

    def __init__(self) -> None:
        # Agent metrics
        self.agent_initializations = MetricCounter()
        self.agent_creation_failures = MetricCounter()
        self.agent_mock_fallbacks = MetricCounter()
        self.agent_active_count = MetricGauge()
        self.agent_orchestration_time = MetricHistogram()

        # Cache metrics
        self.cache_hits = MetricCounter()
        self.cache_misses = MetricCounter()
        self.cache_evictions = MetricCounter()
        self.cache_sets = MetricCounter()
        self.cache_size = MetricGauge()
        self.cache_cleanup_cycles = MetricCounter()

        # Audit metrics
        self.audit_records_created = MetricCounter()
        self.audit_records_approved = MetricCounter()
        self.audit_records_rejected = MetricCounter()
        self.audit_batch_operations = MetricCounter()
        self.audit_pending_timeout = MetricCounter()
        self.audit_rollback_operations = MetricCounter()

        # System metrics
        self.correlation_ids_active = MetricGauge()
        self.async_operations_active = MetricGauge()

        # LLM metrics (from the improvement suggestions)
        self.llm_requests = MetricCounter()
        self.llm_errors = MetricCounter()
        self.llm_duration = MetricHistogram()
        self.llm_tokens = MetricCounter()
        self.error_rate = MetricHistogram()

        # Error metrics
        self.error_counts = {}  # Dictionary to track counts by error type
        self.error_lock = threading.Lock()  # Lock for error tracking

        # TWS-specific metrics
        self.tws_status_requests_success = MetricCounter()
        self.tws_status_requests_failed = MetricCounter()
        self.tws_workstations_total = MetricGauge()
        self.tws_jobs_total = MetricGauge()

        # Connection validation metrics
        self.connection_validations_total = MetricCounter()
        self.connection_validation_success = MetricCounter()
        self.connection_validation_failure = MetricCounter()
        self.health_check_with_auto_enable = MetricCounter()

        # SLO-related metrics
        self.api_response_time = MetricHistogram()  # Track response times for SLO
        self.api_error_rate = MetricGauge()  # Track error rate percentage
        self.system_availability = MetricGauge()  # Track system availability percentage
        self.tws_connection_success_rate = (
            MetricGauge()
        )  # Track TWS connection success rate
        self.ai_agent_response_time = MetricHistogram()  # Track AI agent response times

        # Correlation tracking
        self._correlation_context: Dict[str, Dict[str, Any]] = {}
        self._correlation_lock = (
            threading.Lock()
        )  # Fast operations, safe to use threading.Lock

        # Health monitoring
        self._health_checks: Dict[str, Dict[str, Any]] = {}
        self._health_lock = (
            threading.Lock()
        )  # Fast operations, safe to use threading.Lock

        logger.info("RuntimeMetrics initialized")

    def create_correlation_id(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Create a new correlation ID with optional context."""
        correlation_id = str(uuid.uuid4())
        with self._correlation_lock:
            self._correlation_context[correlation_id] = {
                "created_at": time.time(),
                "context": context or {},
                "operations": [],
            }
            self.correlation_ids_active.set(len(self._correlation_context))
        logger.debug(f"Created correlation ID: {correlation_id}")
        return correlation_id

    def add_correlation_event(
        self, correlation_id: str, event: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an event to a correlation context."""
        with self._correlation_lock:
            if correlation_id in self._correlation_context:
                self._correlation_context[correlation_id]["operations"].append(
                    {
                        "timestamp": time.time(),
                        "event": event,
                        "data": data or {},
                    }
                )

    def close_correlation_id(self, correlation_id: str) -> None:
        """Close a correlation context and log summary."""
        with self._correlation_lock:
            if correlation_id in self._correlation_context:
                context = self._correlation_context.pop(correlation_id)
                duration = time.time() - context["created_at"]
                operation_count = len(context["operations"])

                logger.info(
                    f"Correlation {correlation_id} completed: "
                    f"duration={duration:.2f}s, operations={operation_count}"
                )
                self.correlation_ids_active.set(len(self._correlation_context))

    def record_health_check(
        self, component: str, status: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record health check status for a component."""
        with self._health_lock:
            self._health_checks[component] = {
                "status": status,
                "timestamp": time.time(),
                "details": details or {},
            }
            logger.debug(f"Health check for {component}: {status}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        with self._health_lock:
            return dict(self._health_checks)

    def record_error(self, error_type: str, processing_time: float) -> None:
        """Record error metrics for monitoring and alerting."""
        with self.error_lock:
            if error_type not in self.error_counts:
                self.error_counts[error_type] = MetricCounter()
            self.error_counts[error_type].increment()

        # Also record in histogram for processing time analysis
        self.error_rate.observe(processing_time)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of all current metrics."""
        # Build error metrics
        error_metrics = {}
        with self.error_lock:
            for error_type, counter in self.error_counts.items():
                error_metrics[error_type] = counter.value

        return {
            "agent": {
                "initializations": self.agent_initializations.value,
                "creation_failures": self.agent_creation_failures.value,
                "mock_fallbacks": self.agent_mock_fallbacks.value,
                "active_count": self.agent_active_count.get(),
            },
            "cache": {
                "hits": self.cache_hits.value,
                "misses": self.cache_misses.value,
                "evictions": self.cache_evictions.value,
                "sets": self.cache_sets.value,
                "size": self.cache_size.get(),
                "cleanup_cycles": self.cache_cleanup_cycles.value,
                "hit_rate": (
                    self.cache_hits.value
                    / (self.cache_hits.value + self.cache_misses.value)
                    if (self.cache_hits.value + self.cache_misses.value) > 0
                    else 0
                ),
            },
            "audit": {
                "records_created": self.audit_records_created.value,
                "records_approved": self.audit_records_approved.value,
                "records_rejected": self.audit_records_rejected.value,
                "batch_operations": self.audit_batch_operations.value,
                "pending_timeout": self.audit_pending_timeout.value,
                "rollback_operations": self.audit_rollback_operations.value,
            },
            "system": {
                "correlation_ids_active": self.correlation_ids_active.get(),
                "async_operations_active": self.async_operations_active.get(),
            },
            "slo": {
                "api_error_rate": self._calculate_error_rate(),  # Calculated based on system metrics
                "api_response_time": (
                    self.api_response_time.samples[-1]
                    if self.api_response_time.samples
                    else 0
                ),  # Most recent response time
                "availability": self.system_availability.get(),  # Should be updated by health checks
                "cache_hit_ratio": self._calculate_cache_hit_ratio(),  # Same as cache hit_rate
                "tws_connection_success_rate": self.tws_connection_success_rate.get(),  # Should be updated by TWS connection monitoring
            },
            "errors": error_metrics,
            "health": self.get_health_status(),
        }

    def _calculate_error_rate(self) -> float:
        """Calculate the overall error rate as a percentage."""
        total_requests = (
            self.agent_initializations.value
            + self.tws_status_requests_success.value
            + self.tws_status_requests_failed.value
        )
        if total_requests > 0:
            return (
                self.agent_creation_failures.value
                + self.tws_status_requests_failed.value
            ) / total_requests
        return 0.0

    def _calculate_cache_hit_ratio(self) -> float:
        """Calculate the cache hit ratio."""
        total_cache_ops = self.cache_hits.value + self.cache_misses.value
        if total_cache_ops > 0:
            return self.cache_hits.value / total_cache_ops
        return 0.0

    def update_slo_metrics(
        self,
        availability: Optional[float] = None,
        tws_connection_success_rate: Optional[float] = None,
    ):
        """Update SLO-related metrics that are calculated externally."""
        if availability is not None:
            self.system_availability.set(availability)
        if tws_connection_success_rate is not None:
            self.tws_connection_success_rate.set(tws_connection_success_rate)

    def generate_prometheus_metrics(self) -> str:
        """Generate metrics in Prometheus text exposition format."""
        lines = []
        snapshot = self.get_snapshot()

        for category, metrics in snapshot.items():
            if category == "health":
                continue
            for name, value in metrics.items():
                metric_name = f"resync_{category}_{name}"
                if isinstance(value, (int, float)):
                    lines.append(f"# TYPE {metric_name} gauge")
                    lines.append(f"{metric_name} {value}")

        return "\n".join(lines)


# Global singleton instance
# Lazy initialization of runtime_metrics
_runtime_metrics: Optional[RuntimeMetrics] = None

def _get_runtime_metrics() -> RuntimeMetrics:
    """Lazy initialization of runtime metrics."""
    global _runtime_metrics
    if _runtime_metrics is None:
        _runtime_metrics = RuntimeMetrics()
    return _runtime_metrics

# Backward compatibility - runtime_metrics now uses lazy initialization
# Create a proxy object that behaves like RuntimeMetrics
class _RuntimeMetricsProxy:
    """Proxy object for lazy initialization of RuntimeMetrics."""

    def __init__(self):
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            self._instance = RuntimeMetrics()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)

runtime_metrics = _RuntimeMetricsProxy()


def get_correlation_context() -> str:
    """Get or create correlation ID for current context."""
    # In a real async context, this would use contextvars
    # For now, we'll create a new one if none exists
    return _get_runtime_metrics().create_correlation_id()


def track_llm_metrics(func):
    """
    Decorator to track LLM operation metrics.

    Tracks request count, duration, errors, and token usage.
    Compatible with both sync and async functions.
    """
    import functools
    import inspect

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        runtime_metrics.llm_requests.increment()

        try:
            result = await func(*args, **kwargs)

            # Track duration
            duration = time.time() - start_time
            runtime_metrics.llm_duration.observe(duration)

            # Try to extract token usage from result if available
            if hasattr(result, "usage") and result.usage:
                input_tokens = getattr(result.usage, "prompt_tokens", 0)
                output_tokens = getattr(result.usage, "completion_tokens", 0)
                runtime_metrics.llm_tokens.increment(input_tokens + output_tokens)

            return result

        except Exception:
            runtime_metrics.llm_errors.increment()
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        runtime_metrics.llm_requests.increment()

        try:
            result = func(*args, **kwargs)

            # Track duration
            duration = time.time() - start_time
            runtime_metrics.llm_duration.observe(duration)

            # Try to extract token usage from result if available
            if hasattr(result, "usage") and result.usage:
                input_tokens = getattr(result.usage, "prompt_tokens", 0)
                output_tokens = getattr(result.usage, "completion_tokens", 0)
                runtime_metrics.llm_tokens.increment(input_tokens + output_tokens)

            return result

        except Exception:
            runtime_metrics.llm_errors.increment()
            raise

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def log_with_correlation(
    level: int, message: str, correlation_id: Optional[str] = None, **kwargs: Any
) -> None:
    """Log message with correlation context."""
    if correlation_id:
        runtime_metrics.add_correlation_event(
            correlation_id, f"log_{level}", {"message": message, **kwargs}
        )
    logger.log(level, f"[{correlation_id}] {message}", **kwargs)
