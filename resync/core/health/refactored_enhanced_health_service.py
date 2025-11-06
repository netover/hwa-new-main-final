"""
Refactored Enhanced Health Service

This module provides the refactored enhanced health service using the new
modular architecture with dependency injection and extracted health checkers.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import structlog

from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
)

from .enhanced_health_config_manager import EnhancedHealthConfigurationManager
from .health_checkers.health_checker_factory import HealthCheckerFactory

logger = structlog.get_logger(__name__)


class RefactoredEnhancedHealthService:
    """
    Refactored enhanced health check service using modular components.

    This service integrates all extracted health monitoring components
    using the new architecture with improved maintainability.
    """

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        """
        Initialize the refactored enhanced health service.

        Args:
            config: Optional health check configuration
        """
        self.config_manager = EnhancedHealthConfigurationManager(
            config or HealthCheckConfig()
        )
        self.checker_factory = HealthCheckerFactory(self.config_manager.get_config())
        self.config_manager.set_health_checker_factory(self.checker_factory)

        self.health_history: list[HealthStatusHistory] = []
        self.last_health_check: Optional[datetime] = None

        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0

        # Monitoring control
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("refactored_enhanced_health_check_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        logger.info("refactored_enhanced_health_check_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while self._is_monitoring:
            try:
                await self.perform_comprehensive_health_check()
                await asyncio.sleep(
                    self.config_manager.get_config().check_interval_seconds
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "error_in_refactored_enhanced_health_monitoring_loop", error=str(e)
                )
                await asyncio.sleep(10)  # Brief pause on error

    async def perform_comprehensive_health_check(self) -> HealthCheckResult:
        """
        Perform comprehensive health check using modular health checkers.

        Returns:
            HealthCheckResult: Comprehensive health check results
        """
        start_time = time.time()
        correlation_id = f"refactored_enhanced_health_{int(start_time)}"

        logger.debug(
            "starting_refactored_enhanced_comprehensive_health_check",
            correlation_id=correlation_id,
        )

        # Initialize result
        result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            correlation_id=correlation_id,
            components={},
            summary={},
            alerts=[],
            performance_metrics={},
        )

        # Get enabled health checkers
        enabled_checkers = self.checker_factory.get_enabled_health_checkers()

        # Execute all checks with timeout protection
        check_tasks = {}
        for name, checker in enabled_checkers.items():
            task = asyncio.create_task(
                checker.check_health_with_timeout(),
                name=f"enhanced_health_check_{name}",
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
                "refactored_enhanced_health_check_timed_out",
                timeout_seconds=self.config_manager.get_config().timeout_seconds,
            )
            check_results = [
                asyncio.TimeoutError(f"Health check component {name} timed out")
                for name in check_tasks.keys()
            ]

        # Process results
        for component_name, check_result in zip(
            check_tasks.keys(), check_results, strict=False
        ):
            if isinstance(check_result, Exception):
                logger.error(
                    "refactored_enhanced_health_check_failed",
                    component_name=component_name,
                    error=str(check_result),
                )
                component_health = ComponentHealth(
                    name=component_name,
                    component_type=self.checker_factory.get_component_type_mapping().get(
                        component_name, ComponentType.OTHER
                    ),
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(check_result)}",
                    last_check=datetime.now(),
                )
            else:
                component_health = check_result

            result.components[component_name] = component_health

        # Calculate overall status and summary
        result.overall_status = self._calculate_overall_status(result.components)
        result.summary = self._generate_summary(result.components)
        result.alerts = self._check_alerts(result.components)

        # Record performance metrics
        total_time = (time.time() - start_time) * 1000
        result.performance_metrics = {
            "total_check_time_ms": total_time,
            "components_checked": len(result.components),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_cache_ops": self._cache_hits + self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0
            ),
            "failed_checks": result.summary.get("unhealthy", 0)
            + result.summary.get("unknown", 0),
            "timestamp": time.time(),
        }

        # Update history
        await self._update_health_history(result)
        self.last_health_check = datetime.now()

        logger.debug(
            "refactored_enhanced_health_check_completed",
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

    def _check_alerts(self, components: dict[str, ComponentHealth]) -> list[str]:
        """Check for alerts based on component health status."""
        alerts = []
        for name, comp in components.items():
            if comp.status == HealthStatus.UNHEALTHY:
                alerts.append(f"{name} is unhealthy")
            elif comp.status == HealthStatus.DEGRADED:
                # Include specific threshold breach information in alerts
                if name == "database" and "connection_usage_percent" in comp.metadata:
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

    async def _update_health_history(self, result: HealthCheckResult) -> None:
        """Update health history with new results."""
        # Create history entry
        component_changes = {}
        for name, component in result.components.items():
            # Track status changes (simplified)
            component_changes[name] = component.status

        history_entry = HealthStatusHistory(
            timestamp=result.timestamp,
            overall_status=result.overall_status,
            component_changes=component_changes,
        )

        # Add to history (simplified - no cleanup for now)
        self.health_history.append(history_entry)

    def get_health_history(
        self, hours: int = 24, max_entries: Optional[int] = None
    ) -> list[HealthStatusHistory]:
        """Get health history for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_history = [
            entry for entry in self.health_history if entry.timestamp >= cutoff_time
        ]

        if max_entries and len(filtered_history) > max_entries:
            filtered_history = filtered_history[-max_entries:]

        return filtered_history

    async def attempt_recovery(self, component_name: str) -> bool:
        """Attempt to recover a specific component."""
        logger.info("attempting_recovery_for_component", component_name=component_name)

        try:
            checker = self.checker_factory.get_health_checker(component_name)
            if not checker:
                logger.warning(
                    "unknown_component_for_recovery", component_name=component_name
                )
                return False

            # Perform health check to see if component has recovered
            health = await checker.check_health()
            return health.status == HealthStatus.HEALTHY

        except Exception as e:
            logger.error(
                "refactored_enhanced_recovery_attempt_failed",
                component_name=component_name,
                error=str(e),
            )
            return False

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


# Global refactored enhanced health service instance
_refactored_enhanced_health_service: Optional[RefactoredEnhancedHealthService] = None
_refactored_enhanced_health_service_lock = asyncio.Lock()


async def get_refactored_enhanced_health_service() -> RefactoredEnhancedHealthService:
    """
    Get the global refactored enhanced health service instance.

    Returns:
        RefactoredEnhancedHealthService: The global refactored enhanced health service instance
    """
    global _refactored_enhanced_health_service

    if _refactored_enhanced_health_service is not None:
        return _refactored_enhanced_health_service

    async with _refactored_enhanced_health_service_lock:
        if _refactored_enhanced_health_service is None:
            logger.info("Initializing global refactored enhanced health service")
            _refactored_enhanced_health_service = RefactoredEnhancedHealthService()
            await _refactored_enhanced_health_service.start_monitoring()
            logger.info("Global refactored enhanced health service initialized")

    return _refactored_enhanced_health_service


async def shutdown_refactored_enhanced_health_service() -> None:
    """
    Shutdown the global refactored enhanced health service gracefully.
    """
    global _refactored_enhanced_health_service

    if _refactored_enhanced_health_service is not None:
        try:
            logger.info("Shutting down global refactored enhanced health service")
            await _refactored_enhanced_health_service.stop_monitoring()
            _refactored_enhanced_health_service = None
            logger.info("Global refactored enhanced health service shutdown completed")
        except Exception as e:
            logger.error(
                "Error during refactored enhanced health service shutdown", error=str(e)
            )
            raise
    else:
        logger.debug(
            "Refactored enhanced health service already shutdown or never initialized"
        )
