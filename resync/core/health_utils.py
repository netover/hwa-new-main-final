from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from .health_models import HealthCheckResult, HealthStatus


def initialize_health_result(correlation_id: str) -> HealthCheckResult:
    """
    Initialize a standard health check result object.

    Args:
        correlation_id: Unique identifier for tracking this health check

    Returns:
        HealthCheckResult: Initialized health check result object
    """
    return HealthCheckResult(
        overall_status=HealthStatus.HEALTHY,
        timestamp=datetime.now(),
        correlation_id=correlation_id,
        components={},
        summary={},
        alerts=[],
        performance_metrics={},
    )


def get_health_checks_dict(health_service_instance: Any) -> Dict[str, Any]:
    """
    Get dictionary of all health check coroutines.

    Args:
        health_service_instance: Instance of health service with check methods

    Returns:
        Dict[str, Any]: Dictionary mapping check names to coroutine objects
    """
    return {
        "database": health_service_instance._check_database_health(),
        "redis": health_service_instance._check_redis_health(),
        "cache_hierarchy": health_service_instance._check_cache_health(),
        "file_system": health_service_instance._check_file_system_health(),
        "memory": health_service_instance._check_memory_health(),
        "cpu": health_service_instance._check_cpu_health(),
        "tws_monitor": health_service_instance._check_tws_monitor_health(),
        "connection_pools": health_service_instance._check_connection_pools_health(),
        "websocket_pool": health_service_instance._check_websocket_pool_health(),
    }
