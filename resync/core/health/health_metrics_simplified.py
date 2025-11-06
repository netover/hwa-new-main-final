"""
Simplified Health Metrics for Prometheus

This module provides minimal Prometheus metrics for health checks with low cardinality.
It implements only the essential metrics needed for monitoring health status.
"""

from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from resync.models.health_models import HealthStatus


class SimplifiedHealthMetrics:
    """
    Simplified Prometheus metrics for health checks.

    This class provides only the essential metrics with low cardinality:
    - health_checks_total (Counter, no dynamic labels)
    - health_check_duration_seconds (Histogram, no dynamic labels)
    - component_health (Gauge with a single label component)
    """

    def __init__(self):
        """Initialize simplified health metrics."""
        # Counter for total health checks (no dynamic labels)
        self.health_checks_total = Counter(
            "health_checks_total", "Total number of health checks performed"
        )

        # Histogram for health check duration (no dynamic labels)
        self.health_check_duration_seconds = Histogram(
            "health_check_duration_seconds",
            "Time spent performing health checks",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

        # Gauge for component health status (single label for component name)
        self.component_health = Gauge(
            "component_health",
            "Health status of components (0=UNKNOWN,1=HEALTHY,2=DEGRADED,3=UNHEALTHY)",
            ["component"],
        )

        # Cache for last known component status to avoid unnecessary updates
        self._last_component_status: dict[str, int] = {}

    def record_health_check_start(self) -> None:
        """Record the start of a health check."""
        self.health_checks_total.inc()

    def record_health_check_duration(self, duration_seconds: float) -> None:
        """Record the duration of a health check."""
        self.health_check_duration_seconds.observe(duration_seconds)

    def update_component_health(
        self, component_name: str, status: HealthStatus
    ) -> None:
        """
        Update the health status of a component.

        Args:
            component_name: Name of the component
            status: Health status of the component
        """
        # Convert HealthStatus to numeric value
        status_value = self._status_to_value(status)

        # Only update if status changed to reduce cardinality
        last_status = self._last_component_status.get(component_name)
        if last_status != status_value:
            self.component_health.labels(component=component_name).set(
                status_value
            )
            self._last_component_status[component_name] = status_value

    def _status_to_value(self, status: HealthStatus) -> int:
        """Convert HealthStatus to numeric value for Prometheus."""
        status_map = {
            HealthStatus.UNKNOWN: 0,
            HealthStatus.HEALTHY: 1,
            HealthStatus.DEGRADED: 2,
            HealthStatus.UNHEALTHY: 3,
        }
        return status_map.get(status, 0)

    def get_metrics(self) -> str:
        """
        Get the current Prometheus metrics.

        Returns:
            str: Prometheus metrics in text format
        """
        return generate_latest().decode('utf-8')

    def get_content_type(self) -> str:
        """
        Get the content type for Prometheus metrics.

        Returns:
            str: Content type for Prometheus metrics
        """
        return CONTENT_TYPE_LATEST


# Global instance for simplified health metrics
_health_metrics: SimplifiedHealthMetrics | None = None


def get_health_metrics() -> SimplifiedHealthMetrics:
    """
    Get global simplified health metrics instance.

    Returns:
        SimplifiedHealthMetrics: The global health metrics instance
    """
    global _health_metrics
    if _health_metrics is None:
        _health_metrics = SimplifiedHealthMetrics()
    return _health_metrics


def record_health_check_with_timing(
    component_name: str, status: HealthStatus
) -> float:
    """
    Record a health check with timing.

    This is a convenience function that records the start, duration,
    and updates the component health status.

    Args:
        component_name: Name of the component
        status: Health status of the component

    Returns:
        float: Duration of the health check in seconds
    """
    metrics = get_health_metrics()
    start_time = time.time()

    # Record the check start
    metrics.record_health_check_start()

    # Update component health
    metrics.update_component_health(component_name, status)

    # Calculate and record duration
    duration = time.time() - start_time
    metrics.record_health_check_duration(duration)

    return duration




