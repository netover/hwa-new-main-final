"""
Refactored Health Check Service

This module provides the refactored basic health check service using the new
modular architecture with dependency injection and extracted health checkers.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import structlog

from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    SystemHealthStatus,
)

from .enhanced_health_config_manager import EnhancedHealthConfigurationManager
from .health_checkers.health_checker_factory import HealthCheckerFactory

logger = structlog.get_logger(__name__)


class RefactoredHealthCheckService:
    """
    Refactored core health check service using modular health checkers.

    This service provides basic health checking functionality using
    the new architecture with improved modularity and maintainability.
    """

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        """
        Initialize the refactored health check service.

        Args:
            config: Optional health check configuration
        """
        self.config_manager = EnhancedHealthConfigurationManager(
            config or HealthCheckConfig()
        )
        self.checker_factory = HealthCheckerFactory(self.config_manager.get_config())
        self.config_manager.set_health_checker_factory(self.checker_factory)

        self._component_cache: dict[str, ComponentHealth] = {}
        self._last_system_check: Optional[datetime] = None

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """
        Run health checks on all enabled system components.

        Returns:
            List[HealthCheckResult]: List of health check results for all components
        """
        results = []

        # Get enabled health checkers
        enabled_checkers = self.checker_factory.get_enabled_health_checkers()

        for component_name, checker in enabled_checkers.items():
            try:
                # Perform health check using the modular checker
                health = await checker.check_health_with_timeout()

                # Create result
                result = HealthCheckResult(
                    overall_status=health.status,
                    timestamp=datetime.now(),
                    correlation_id=f"refactored_health_check_{component_name}_{int(time.time())}",
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
                    component_type=checker.component_type,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(e)}",
                    last_check=datetime.now(),
                    error_count=1,
                )

                error_result = HealthCheckResult(
                    overall_status=HealthStatus.UNKNOWN,
                    timestamp=datetime.now(),
                    correlation_id=f"refactored_health_check_{component_name}_error_{int(time.time())}",
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

        # Get checker and perform fresh health check
        checker = self.checker_factory.get_health_checker(component_name)
        if not checker:
            raise ValueError(
                f"No health checker available for component: {component_name}"
            )

        health = await checker.check_health_with_timeout()

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

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_components": len(self._component_cache),
            "last_system_check": (
                self._last_system_check.isoformat() if self._last_system_check else None
            ),
        }

    def clear_cache(self) -> None:
        """Clear the component health cache."""
        self._component_cache.clear()
        logger.info("refactored_health_check_cache_cleared")

    def get_config_summary(self) -> dict[str, Any]:
        """Get configuration summary."""
        return self.config_manager.get_config_summary_enhanced()

    def validate_configuration(self) -> dict[str, Any]:
        """Validate current configuration."""
        return {
            "config_validation": self.config_manager.validate_config(),
            "checker_validation": self.config_manager.validate_all_checkers_config(),
            "is_valid": (
                len(self.config_manager.validate_config()) == 0
                and all(
                    len(errors) == 0
                    for errors in self.config_manager.validate_all_checkers_config().values()
                )
            ),
        }
