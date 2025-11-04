"""Minimal health service implementation for tests."""

from __future__ import annotations

from dataclasses import dataclass

from resync.core.health_models import ComponentHealth, ComponentType, HealthCheckConfig, HealthStatus
from resync.core.pools.pool_manager import get_connection_pool_manager


class HealthCheckService:
    def __init__(self, config: HealthCheckConfig | None = None) -> None:
        self.config = config or HealthCheckConfig()

    async def _check_database_health(self) -> ComponentHealth:
        manager = await get_connection_pool_manager()
        stats_map = manager.get_pool_stats()
        stats = stats_map.get("database")
        threshold = getattr(self.config, "database_connection_threshold_percent", 90.0)
        if stats is None or stats.total_connections == 0:
            return ComponentHealth(
                name="database_connections",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNKNOWN,
                message="Database pool not configured",
                metadata={"threshold_percent": threshold},
            )
        usage = (stats.active_connections / stats.total_connections) * 100
        metadata = {
            "active_connections": stats.active_connections,
            "idle_connections": stats.idle_connections,
            "total_connections": stats.total_connections,
            "connection_usage_percent": usage,
            "threshold_percent": threshold,
        }
        if usage >= threshold:
            status = HealthStatus.DEGRADED if usage < 100 else HealthStatus.CRITICAL
            message = "Database connection usage above threshold"
        else:
            status = HealthStatus.HEALTHY
            message = "Database connection usage healthy"
        return ComponentHealth(
            name="database_connections",
            component_type=ComponentType.DATABASE,
            status=status,
            message=message,
            metadata=metadata,
        )


__all__ = ["HealthCheckService"]
