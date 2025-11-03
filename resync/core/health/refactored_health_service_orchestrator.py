"""
Refactored Health Service Orchestrator

This module provides the refactored health service orchestrator using the new
modular architecture with dependency injection and extracted health checkers.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

import structlog
from resync.models.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
)

from .enhanced_health_config_manager import EnhancedHealthConfigurationManager
from .health_checkers.health_checker_factory import HealthCheckerFactory

logger = structlog.get_logger(__name__)


class RefactoredHealthServiceOrchestrator:
    """
    Refactored orchestrator that uses dependency injection and modular health checkers.

    This class provides the main coordination logic for health checks using
    the new architecture with improved modularity and maintainability.
    """

    def __init__(self, config: HealthCheckConfig | None = None):
        """
        Initialize the refactored health service orchestrator.

        Args:
            config: Health check configuration (uses default if None)
        """
        self.config_manager = EnhancedHealthConfigurationManager(
            config or HealthCheckConfig()
        )
        self.checker_factory = HealthCheckerFactory(
            self.config_manager.get_config()
        )
        self.config_manager.set_health_checker_factory(self.checker_factory)

        self.last_health_check: datetime | None = None
        self._component_results: dict[str, ComponentHealth] = {}
        self._lock = asyncio.Lock()

        # Performance tracking
        self._performance_metrics = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "average_response_time": 0.0,
        }

    async def perform_comprehensive_health_check(
        self,
        proactive_monitor: Any | None = None,
        performance_collector: Any | None = None,
        cache_manager: Any | None = None,
    ) -> HealthCheckResult:
        """
        Perform comprehensive health check using modular health checkers.

        Args:
            proactive_monitor: Proactive monitoring component
            performance_collector: Performance metrics collector
            cache_manager: Component cache manager

        Returns:
            Comprehensive health check result
        """
        start_time = time.time()
        correlation_id = f"refactored_health_{int(start_time)}"

        logger.debug(
            "starting_refactored_comprehensive_health_check",
            correlation_id=correlation_id,
        )

        # Initialize result with enhanced metadata
        result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            correlation_id=correlation_id,
            components={},
            summary={},
            alerts=[],
            performance_metrics={},
        )

        # Collect performance metrics if available
        performance_metrics = {}
        connection_pool_stats = {}

        if performance_collector:
            try:
                performance_metrics = (
                    await performance_collector.get_system_performance_metrics()
                )
                pool_metrics = (
                    await performance_collector.get_connection_pool_metrics()
                )
                if "error" not in pool_metrics:
                    connection_pool_stats = pool_metrics
            except Exception as e:
                logger.warning(
                    "failed_to_collect_performance_metrics", error=str(e)
                )

        result.metadata = {
            "check_start_time": start_time,
            "proactive_checks": proactive_monitor is not None,
            "performance_metrics": performance_metrics,
            "connection_pool_stats": connection_pool_stats,
        }

        # Get enabled health checkers
        enabled_checkers = self.checker_factory.get_enabled_health_checkers()

        # Execute all checks with timeout protection
        check_tasks = {}
        for name, checker in enabled_checkers.items():
            task = asyncio.create_task(
                checker.check_health_with_timeout(),
                name=f"health_check_{name}",
            )
            check_tasks[name] = task

        # Wait for all checks to complete with global timeout
        try:
            check_results = await asyncio.wait_for(
                asyncio.gather(*check_tasks.values(), return_exceptions=True),
                timeout=self.config_manager.get_config().timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "health_check_timed_out",
                timeout_seconds=self.config_manager.get_config().timeout_seconds,
            )
            check_results = [
                asyncio.TimeoutError(
                    f"Health check component {name} timed out"
                )
                for name in check_tasks
            ]

        # Process results
        for component_name, check_result in zip(
            check_tasks.keys(), check_results, strict=False
        ):
            if isinstance(check_result, Exception):
                # Handle check failure
                logger.error(
                    "refactored_health_check_failed",
                    component_name=component_name,
                    error=str(check_result),
                )

                # Create error component health
                error_health = ComponentHealth(
                    name=component_name,
                    component_type=self.checker_factory.get_component_type_mapping().get(
                        component_name, ComponentType.OTHER
                    ),
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(check_result)}",
                    last_check=datetime.now(),
                )

                # For timeout errors specifically, mark as unhealthy
                if isinstance(check_result, asyncio.TimeoutError):
                    error_health.status = HealthStatus.UNHEALTHY
                    error_health.message = (
                        f"Check timeout: {str(check_result)}"
                    )

                result.components[component_name] = error_health
            else:
                result.components[component_name] = check_result

        # Calculate overall status and summary
        result.overall_status = self._calculate_overall_status(
            result.components
        )
        result.summary = self._generate_summary(result.components)

        # Check for alerts if alerting is enabled
        if self.config_manager.get_config().alert_enabled:
            result.alerts = self._check_alerts(result.components)

        # Record performance metrics
        total_time = (time.time() - start_time) * 1000
        result.performance_metrics = {
            "total_check_time_ms": total_time,
            "components_checked": len(result.components),
            "timestamp": time.time(),
        }

        # Update component results cache
        async with self._lock:
            self._component_results = result.components.copy()

        # Update performance tracking
        self._update_performance_metrics(result)

        self.last_health_check = datetime.now()

        logger.debug(
            "refactored_health_check_completed",
            total_check_time_ms=total_time,
        )

        return result

    def _calculate_overall_status(
        self, components: dict[str, ComponentHealth]
    ) -> HealthStatus:
        """Calculate overall health status from component results."""
        # Simple aggregation: worst status wins
        priority = {
            HealthStatus.UNHEALTHY: 3,
            HealthStatus.DEGRADED: 2,
            HealthStatus.UNKNOWN: 1,
            HealthStatus.HEALTHY: 0,
        }
        worst = HealthStatus.HEALTHY
        for comp in components.values():
            if priority[comp.status] > priority[worst]:
                worst = comp.status
        return worst

    def _generate_summary(
        self, components: dict[str, ComponentHealth]
    ) -> dict[str, int]:
        """Generate summary of health status counts."""
        summary = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0,
        }
        for comp in components.values():
            if comp.status == HealthStatus.HEALTHY:
                summary["healthy"] += 1
            elif comp.status == HealthStatus.DEGRADED:
                summary["degraded"] += 1
            elif comp.status == HealthStatus.UNHEALTHY:
                summary["unhealthy"] += 1
            else:
                summary["unknown"] += 1
        return summary

    def _check_alerts(
        self, components: dict[str, ComponentHealth]
    ) -> list[str]:
        """Check for alerts based on component health status."""
        alerts = []
        for name, comp in components.items():
            if comp.status == HealthStatus.UNHEALTHY:
                alerts.append(f"{name} is unhealthy")
            elif comp.status == HealthStatus.DEGRADED:
                # Include specific threshold breach information in alerts
                if (
                    name == "database"
                    and "connection_usage_percent" in comp.metadata
                ):
                    threshold = comp.metadata.get(
                        "threshold_percent",
                        self.config_manager.get_config().database_connection_threshold_percent,
                    )
                    usage = comp.metadata["connection_usage_percent"]
                    alerts.append(
                        f"Database connection pool usage at {usage:.1f}% (threshold: {threshold}%)"
                    )
                else:
                    alerts.append(f"{name} is degraded")
        return alerts

    def _update_performance_metrics(self, result: HealthCheckResult) -> None:
        """Update internal performance metrics."""
        self._performance_metrics["total_checks"] += 1

        failed_count = result.summary.get("unhealthy", 0) + result.summary.get(
            "unknown", 0
        )
        if failed_count == 0:
            self._performance_metrics["successful_checks"] += 1
        else:
            self._performance_metrics["failed_checks"] += 1

        # Update average response time
        total_time = result.performance_metrics.get("total_check_time_ms", 0)
        current_avg = self._performance_metrics["average_response_time"]
        count = self._performance_metrics["total_checks"]

        self._performance_metrics["average_response_time"] = (
            (current_avg * (count - 1)) + total_time
        ) / count

    async def get_component_health(
        self, component_name: str
    ) -> ComponentHealth | None:
        """Get the current health status of a specific component."""
        async with self._lock:
            return self._component_results.get(component_name)

    async def get_all_component_health(self) -> dict[str, ComponentHealth]:
        """Get all current component health results."""
        async with self._lock:
            return self._component_results.copy()

    def get_last_check_time(self) -> datetime | None:
        """Get the timestamp of the last health check."""
        return self.last_health_check

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for the orchestrator."""
        return self._performance_metrics.copy()

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




