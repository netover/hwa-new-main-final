"""
Health Utilities Module

This module provides utility functions for health checking operations.
"""

from __future__ import annotations

from datetime import datetime

from resync.models.health_models import HealthCheckResult


def initialize_health_result(correlation_id: str | None = None) -> HealthCheckResult:
    """
    Initialize a new health check result with default values.

    Args:
        correlation_id: Optional correlation ID for tracing

    Returns:
        Initialized HealthCheckResult instance
    """
    return HealthCheckResult(
        overall_status=None,  # Will be set later
        timestamp=datetime.now(),
        correlation_id=correlation_id,
        components={},
        summary={},
        alerts=[],
        performance_metrics={}
    )


def format_health_summary(result: HealthCheckResult) -> dict[str, any]:
    """
    Format a health check result into a summary dictionary.

    Args:
        result: Health check result to format

    Returns:
        Formatted summary dictionary
    """
    return {
        "overall_status": result.overall_status,
        "timestamp": result.timestamp.isoformat() if result.timestamp else None,
        "correlation_id": result.correlation_id,
        "total_components": len(result.components),
        "healthy_components": sum(1 for c in result.components.values() if c.status.name == "HEALTHY"),
        "unhealthy_components": sum(1 for c in result.components.values() if c.status.name != "HEALTHY"),
        "alerts_count": len(result.alerts),
        "performance_metrics": result.performance_metrics,
    }
