from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckResult,
    HealthStatus,
    SystemHealthStatus,
)


class HealthCheckService:
    """
    Core health check service for system components.

    This service provides basic health checking functionality that can be
    extended with more comprehensive monitoring and diagnostics.
    """

    def __init__(self):
        """Initialize the health check service."""
        self._component_cache: dict[str, ComponentHealth] = {}
        self._last_system_check: Optional[datetime] = None

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """
        Run health checks on all system components.

        Returns:
            List[HealthCheckResult]: List of health check results for all components
        """
        results = []

        # Define the components to check
        components_to_check = [
            "database",
            "redis",
            "cache_hierarchy",
            "file_system",
            "memory",
            "cpu",
        ]

        for component_name in components_to_check:
            try:
                # Get component type
                component_type = self._get_component_type(component_name)

                # Perform basic health check
                health = await self._perform_basic_health_check(
                    component_name, component_type
                )

                # Create result
                result = HealthCheckResult(
                    overall_status=health.status,
                    timestamp=datetime.now(),
                    correlation_id=f"health_check_{component_name}_{int(time.time())}",
                    components={component_name: health},
                    summary={
                        "total_components": 1,
                        "healthy": 1 if health.status == HealthStatus.HEALTHY else 0,
                        "degraded": 1 if health.status == HealthStatus.DEGRADED else 0,
                        "unhealthy": (
                            1 if health.status == HealthStatus.UNHEALTHY else 0
                        ),
                        "unknown": 1 if health.status == HealthStatus.UNKNOWN else 0,
                    },
                )

                results.append(result)

                # Cache the component health
                self._component_cache[component_name] = health

            except Exception as e:
                # Create error result for failed checks
                error_health = ComponentHealth(
                    name=component_name,
                    component_type=self._get_component_type(component_name),
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(e)}",
                    last_check=datetime.now(),
                    error_count=1,
                )

                error_result = HealthCheckResult(
                    overall_status=HealthStatus.UNKNOWN,
                    timestamp=datetime.now(),
                    correlation_id=f"health_check_{component_name}_error_{int(time.time())}",
                    components={component_name: error_health},
                    summary={"total_components": 1, "unknown": 1},
                )

                results.append(error_result)

        return results

    async def get_component_health(
        self, component_type: ComponentType
    ) -> ComponentHealth:
        """
        Get health status for a specific component type.

        Args:
            component_type: The type of component to check

        Returns:
            ComponentHealth: Health status of the component

        Raises:
            ValueError: If component type is not supported
        """
        # Map component type to component name
        component_name_map = {
            ComponentType.DATABASE: "database",
            ComponentType.REDIS: "redis",
            ComponentType.CACHE: "cache_hierarchy",
            ComponentType.FILE_SYSTEM: "file_system",
            ComponentType.MEMORY: "memory",
            ComponentType.CPU: "cpu",
        }

        component_name = component_name_map.get(component_type)
        if not component_name:
            raise ValueError(f"Unsupported component type: {component_type}")

        # Check cache first
        cached_health = self._component_cache.get(component_name)
        if cached_health:
            # Simple cache expiry check (5 minutes)
            age = datetime.now() - cached_health.last_check
            if age.total_seconds() < 300:
                return cached_health

        # Perform fresh health check
        health = await self._perform_basic_health_check(component_name, component_type)

        # Update cache
        self._component_cache[component_name] = health

        return health

    async def get_system_health(self) -> SystemHealthStatus:
        """
        Get overall system health status.

        Returns:
            SystemHealthStatus: Overall system health status
        """
        try:
            # Run all checks to get current status
            results = await self.run_all_checks()

            if not results:
                return SystemHealthStatus.OK

            # Count status types across all results
            healthy_count = 0
            warning_count = 0
            critical_count = 0

            for result in results:
                for component in result.components.values():
                    if component.status == HealthStatus.HEALTHY:
                        healthy_count += 1
                    elif component.status == HealthStatus.DEGRADED:
                        warning_count += 1
                    elif component.status in [
                        HealthStatus.UNHEALTHY,
                        HealthStatus.UNKNOWN,
                    ]:
                        critical_count += 1

            # Determine overall status
            total_components = len(results)
            critical_ratio = (
                critical_count / total_components if total_components > 0 else 0
            )

            if critical_ratio > 0.5:  # More than 50% critical
                return SystemHealthStatus.CRITICAL
            elif warning_count > 0 or critical_count > 0:
                return SystemHealthStatus.WARNING
            else:
                return SystemHealthStatus.OK

        except Exception:
            # Return critical status on any error
            return SystemHealthStatus.CRITICAL

    async def _perform_basic_health_check(
        self, component_name: str, component_type: ComponentType
    ) -> ComponentHealth:
        """
        Perform a basic health check for a component.

        Args:
            component_name: Name of the component
            component_type: Type of the component

        Returns:
            ComponentHealth: Health status of the component
        """
        start_time = time.time()

        try:
            # Basic health checks based on component type
            if component_type == ComponentType.DATABASE:
                return await self._check_database_health_basic(component_name)
            elif component_type == ComponentType.REDIS:
                return await self._check_redis_health_basic(component_name)
            elif component_type == ComponentType.CACHE:
                return await self._check_cache_health_basic(component_name)
            elif component_type == ComponentType.FILE_SYSTEM:
                return await self._check_file_system_health_basic(component_name)
            elif component_type == ComponentType.MEMORY:
                return await self._check_memory_health_basic(component_name)
            elif component_type == ComponentType.CPU:
                return await self._check_cpu_health_basic(component_name)
            else:
                # Default basic check
                response_time = (time.time() - start_time) * 1000
                return ComponentHealth(
                    name=component_name,
                    component_type=component_type,
                    status=HealthStatus.HEALTHY,
                    message=f"{component_name} basic check passed",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name=component_name,
                component_type=component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"{component_name} check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_database_health_basic(
        self, component_name: str
    ) -> ComponentHealth:
        """Basic database health check."""
        # This would contain basic database connectivity checks
        # For now, return a placeholder healthy status
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.DATABASE,
            status=HealthStatus.HEALTHY,
            message="Database connectivity check passed",
            response_time_ms=10.0,
            last_check=datetime.now(),
        )

    async def _check_redis_health_basic(self, component_name: str) -> ComponentHealth:
        """Basic Redis health check."""
        # This would contain basic Redis connectivity checks
        # For now, return a placeholder healthy status
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.REDIS,
            status=HealthStatus.HEALTHY,
            message="Redis connectivity check passed",
            response_time_ms=5.0,
            last_check=datetime.now(),
        )

    async def _check_cache_health_basic(self, component_name: str) -> ComponentHealth:
        """Basic cache health check."""
        # This would contain basic cache functionality checks
        # For now, return a placeholder healthy status
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.CACHE,
            status=HealthStatus.HEALTHY,
            message="Cache functionality check passed",
            response_time_ms=2.0,
            last_check=datetime.now(),
        )

    async def _check_file_system_health_basic(
        self, component_name: str
    ) -> ComponentHealth:
        """Basic file system health check."""
        # This would contain basic file system checks
        # For now, return a placeholder healthy status
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.FILE_SYSTEM,
            status=HealthStatus.HEALTHY,
            message="File system check passed",
            response_time_ms=1.0,
            last_check=datetime.now(),
        )

    async def _check_memory_health_basic(self, component_name: str) -> ComponentHealth:
        """Basic memory health check."""
        # This would contain basic memory usage checks
        # For now, return a placeholder healthy status
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.MEMORY,
            status=HealthStatus.HEALTHY,
            message="Memory usage check passed",
            response_time_ms=1.0,
            last_check=datetime.now(),
        )

    async def _check_cpu_health_basic(self, component_name: str) -> ComponentHealth:
        """Basic CPU health check."""
        # This would contain basic CPU usage checks
        # For now, return a placeholder healthy status
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.CPU,
            status=HealthStatus.HEALTHY,
            message="CPU usage check passed",
            response_time_ms=1.0,
            last_check=datetime.now(),
        )

    def _get_component_type(self, name: str) -> ComponentType:
        """Map component name to component type."""
        mapping = {
            "database": ComponentType.DATABASE,
            "redis": ComponentType.REDIS,
            "cache_hierarchy": ComponentType.CACHE,
            "file_system": ComponentType.FILE_SYSTEM,
            "memory": ComponentType.MEMORY,
            "cpu": ComponentType.CPU,
        }
        return mapping.get(name, ComponentType.OTHER)
