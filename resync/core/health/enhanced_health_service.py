"""
Enhanced Health Service

This module provides an enhanced health service that integrates all the
extracted health monitoring components into a cohesive health checking
system with improved modularity and maintainability.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
)
from resync.settings import settings

# Import extracted components
from .circuit_breaker import CircuitBreaker
from .health_check_utils import HealthCheckUtils
from .proactive_monitor import ProactiveHealthMonitor
from .monitors.cache_monitor import CacheHierarchyHealthMonitor
from .monitors.connection_monitor import ConnectionPoolMonitor
from .monitors.redis_monitor import RedisHealthMonitor
from .monitors.system_monitor import SystemResourceMonitor
from .monitors.tws_monitor import TWSMonitorHealthChecker

logger = structlog.get_logger(__name__)


class EnhancedHealthService:
    """
    Enhanced health check service using modular components.

    This service integrates all extracted health monitoring components
    to provide comprehensive health checking with improved maintainability.
    """

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        """
        Initialize the enhanced health service.

        Args:
            config: Optional health check configuration
        """
        self.config = config or HealthCheckConfig()
        self.health_history: List[HealthStatusHistory] = []
        self.last_health_check: Optional[datetime] = None

        # Initialize component monitors
        self.redis_monitor = RedisHealthMonitor()
        self.cache_monitor = CacheHierarchyHealthMonitor()
        self.system_monitor = SystemResourceMonitor()
        self.connection_monitor = ConnectionPoolMonitor()
        self.tws_monitor = TWSMonitorHealthChecker()
        self.proactive_monitor = ProactiveHealthMonitor()

        # Circuit breakers for critical components
        self._circuit_breakers = {
            "database": CircuitBreaker(name="database"),
            "redis": CircuitBreaker(name="redis"),
            "cache_hierarchy": CircuitBreaker(name="cache_hierarchy"),
            "tws_monitor": CircuitBreaker(name="tws_monitor"),
        }

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
        logger.info("enhanced_health_check_monitoring_started")

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
        logger.info("enhanced_health_check_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while self._is_monitoring:
            try:
                await self.perform_comprehensive_health_check()
                await asyncio.sleep(self.config.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error_in_enhanced_health_monitoring_loop", error=str(e))
                await asyncio.sleep(10)  # Brief pause on error

    async def perform_comprehensive_health_check(self) -> HealthCheckResult:
        """
        Perform comprehensive health check using all extracted components.

        Returns:
            HealthCheckResult: Comprehensive health check results
        """
        start_time = time.time()
        correlation_id = f"enhanced_health_{int(start_time)}"

        logger.debug(
            "starting_enhanced_comprehensive_health_check",
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

        # Perform all health checks using extracted components
        health_checks = {
            "database": self._check_database_health,
            "redis": self._check_redis_health,
            "cache_hierarchy": self._check_cache_health,
            "file_system": self._check_file_system_health,
            "memory": self._check_memory_health,
            "cpu": self._check_cpu_health,
            "tws_monitor": self._check_tws_monitor_health,
            "connection_pools": self._check_connection_pools_health,
            "websocket_pool": self._check_websocket_pool_health,
        }

        # Execute all checks with timeout protection
        try:
            check_tasks = {
                name: asyncio.create_task(check_func())
                for name, check_func in health_checks.items()
            }

            check_results = await asyncio.wait_for(
                asyncio.gather(*check_tasks.values(), return_exceptions=True),
                timeout=30.0,  # 30 second global timeout
            )
        except asyncio.TimeoutError:
            logger.error("enhanced_health_check_timed_out", timeout_seconds=30)
            check_results = [
                asyncio.TimeoutError(f"Health check component {name} timed out")
                for name in health_checks.keys()
            ]

        # Process results
        for component_name, check_result in zip(
            health_checks.keys(), check_results, strict=False
        ):
            if isinstance(check_result, Exception):
                logger.error(
                    "enhanced_health_check_failed",
                    component_name=component_name,
                    error=str(check_result),
                )
                component_health = ComponentHealth(
                    name=component_name,
                    component_type=HealthCheckUtils.get_component_type(component_name),
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(check_result)}",
                    last_check=datetime.now(),
                )
            else:
                component_health = check_result

            result.components[component_name] = component_health

        # Calculate overall status and summary
        result.overall_status = HealthCheckUtils.calculate_overall_status(
            result.components
        )
        result.summary = HealthCheckUtils.generate_summary(result.components)
        result.alerts = HealthCheckUtils.check_alerts(result.components)

        # Record performance metrics
        result.performance_metrics = {
            "total_check_time_ms": (time.time() - start_time) * 1000,
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
            "enhanced_health_check_completed",
            total_check_time_ms=result.performance_metrics["total_check_time_ms"],
        )

        return result

    async def _check_database_health(self) -> ComponentHealth:
        """Check database health using connection pools."""
        try:
            # Use circuit breaker for database checks
            async def db_check():
                pool_manager = get_connection_pool_manager()
                if not pool_manager:
                    return ComponentHealth(
                        name="database",
                        component_type=ComponentType.DATABASE,
                        status=HealthStatus.UNKNOWN,
                        message="Database connection pool not available",
                        last_check=datetime.now(),
                    )

                # Test database connectivity
                async with pool_manager.acquire_connection("default") as conn:
                    if hasattr(conn, "execute"):
                        result = await conn.execute("SELECT 1")
                        if hasattr(result, "fetchone"):
                            await result.fetchone()
                    elif hasattr(conn, "cursor"):
                        cursor = await conn.cursor()
                        await cursor.execute("SELECT 1")
                        await cursor.fetchone()
                        await cursor.close()

                # Get pool statistics
                pool_stats = pool_manager.get_pool_stats()
                db_pool_stats = pool_stats.get("database") if pool_stats else None

                if not db_pool_stats or db_pool_stats.total_connections == 0:
                    return ComponentHealth(
                        name="database",
                        component_type=ComponentType.DATABASE,
                        status=HealthStatus.UNHEALTHY,
                        message="Database pool has no configured connections",
                        last_check=datetime.now(),
                    )

                # Calculate connection usage
                active_connections = db_pool_stats.active_connections
                total_connections = db_pool_stats.total_connections
                connection_usage_percent = active_connections / total_connections * 100

                # Determine status
                threshold_percent = self.config.database_connection_threshold_percent
                if connection_usage_percent > threshold_percent:
                    status = HealthStatus.DEGRADED
                    message = f"Database connection pool near capacity: {active_connections}/{total_connections} ({connection_usage_percent:.1f}%)"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Database connection pool healthy: {active_connections}/{total_connections} ({connection_usage_percent:.1f}%)"

                return ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=status,
                    message=message,
                    response_time_ms=100,  # Placeholder
                    last_check=datetime.now(),
                    metadata={
                        "active_connections": active_connections,
                        "total_connections": total_connections,
                        "connection_usage_percent": round(connection_usage_percent, 1),
                        "threshold_percent": threshold_percent,
                    },
                )

            return await self._circuit_breakers["database"].call(db_check)

        except Exception as e:
            logger.error("enhanced_database_health_check_failed", error=str(e))
            return ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_redis_health(self) -> ComponentHealth:
        """Check Redis health using extracted monitor."""
        try:
            return await self.redis_monitor.check_redis_health_with_retry()
        except Exception as e:
            logger.error("enhanced_redis_health_check_failed", error=str(e))
            return ComponentHealth(
                name="redis",
                component_type=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check failed: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cache_health(self) -> ComponentHealth:
        """Check cache health using extracted monitor."""
        try:
            return await self.cache_monitor.check_cache_health_with_retry()
        except Exception as e:
            logger.error("enhanced_cache_health_check_failed", error=str(e))
            return ComponentHealth(
                name="cache_hierarchy",
                component_type=ComponentType.CACHE,
                status=HealthStatus.DEGRADED,
                message=f"Cache hierarchy issues: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_file_system_health(self) -> ComponentHealth:
        """Check file system health."""
        # Use existing filesystem monitor if available
        from .monitors.filesystem_monitor import FileSystemHealthMonitor

        monitor = FileSystemHealthMonitor()
        disk_status = monitor.check_disk_space()

        return ComponentHealth(
            name="file_system",
            component_type=ComponentType.FILE_SYSTEM,
            status=disk_status.status,
            message=disk_status.status.value,
            response_time_ms=10,  # Placeholder
            last_check=datetime.now(),
            metadata={
                "disk_usage_percent": disk_status.used_percent,
                "disk_free_gb": disk_status.free_bytes / (1024**3),
                "mount_point": disk_status.mount_point,
            },
        )

    async def _check_memory_health(self) -> ComponentHealth:
        """Check memory health using extracted monitor."""
        try:
            return await self.system_monitor.check_memory_health()
        except Exception as e:
            logger.error("enhanced_memory_health_check_failed", error=str(e))
            return ComponentHealth(
                name="memory",
                component_type=ComponentType.MEMORY,
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cpu_health(self) -> ComponentHealth:
        """Check CPU health using extracted monitor."""
        try:
            return await self.system_monitor.check_cpu_health()
        except Exception as e:
            logger.error("enhanced_cpu_health_check_failed", error=str(e))
            return ComponentHealth(
                name="cpu",
                component_type=ComponentType.CPU,
                status=HealthStatus.UNKNOWN,
                message=f"CPU check failed: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_tws_monitor_health(self) -> ComponentHealth:
        """Check TWS monitor health using extracted checker."""
        try:
            return await self.tws_monitor.check_tws_monitor_health()
        except Exception as e:
            logger.error("enhanced_tws_monitor_health_check_failed", error=str(e))
            return ComponentHealth(
                name="tws_monitor",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.UNHEALTHY,
                message=f"TWS monitor connectivity failed: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_connection_pools_health(self) -> ComponentHealth:
        """Check connection pools health using extracted monitor."""
        try:
            return await self.connection_monitor.check_connection_pools_health()
        except Exception as e:
            logger.error("enhanced_connection_pools_health_check_failed", error=str(e))
            return ComponentHealth(
                name="connection_pools",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection pools check failed: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_websocket_pool_health(self) -> ComponentHealth:
        """Check WebSocket pool health using extracted monitor."""
        try:
            return await self.connection_monitor.check_websocket_pool_health()
        except Exception as e:
            logger.error("enhanced_websocket_pool_health_check_failed", error=str(e))
            return ComponentHealth(
                name="websocket_pool",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"WebSocket pool unavailable: {str(e)}",
                last_check=datetime.now(),
                error_count=1,
            )

    async def perform_proactive_health_checks(self) -> Dict[str, Any]:
        """
        Perform proactive health checks using extracted monitor.

        Returns:
            Dictionary containing proactive health check results
        """
        return await self.proactive_monitor.perform_proactive_health_checks()

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
    ) -> List[HealthStatusHistory]:
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
            if component_name == "database":
                health = await self._check_database_health()
            elif component_name == "redis":
                health = await self._check_redis_health()
            elif component_name == "cache_hierarchy":
                health = await self._check_cache_health()
            elif component_name == "memory":
                health = await self._check_memory_health()
            elif component_name == "cpu":
                health = await self._check_cpu_health()
            else:
                logger.warning(
                    "unknown_component_for_recovery", component_name=component_name
                )
                return False

            return health.status == HealthStatus.HEALTHY

        except Exception as e:
            logger.error(
                "enhanced_recovery_attempt_failed",
                component_name=component_name,
                error=str(e),
            )
            return False


# Global enhanced health service instance
_enhanced_health_service: Optional[EnhancedHealthService] = None
_enhanced_health_service_lock = asyncio.Lock()


async def get_enhanced_health_service() -> EnhancedHealthService:
    """
    Get the global enhanced health service instance.

    Returns:
        EnhancedHealthService: The global enhanced health service instance
    """
    global _enhanced_health_service

    if _enhanced_health_service is not None:
        return _enhanced_health_service

    async with _enhanced_health_service_lock:
        if _enhanced_health_service is None:
            logger.info("Initializing global enhanced health service")
            _enhanced_health_service = EnhancedHealthService()
            await _enhanced_health_service.start_monitoring()
            logger.info("Global enhanced health service initialized")

    return _enhanced_health_service


async def shutdown_enhanced_health_service() -> None:
    """
    Shutdown the global enhanced health service gracefully.
    """
    global _enhanced_health_service

    if _enhanced_health_service is not None:
        try:
            logger.info("Shutting down global enhanced health service")
            await _enhanced_health_service.stop_monitoring()
            _enhanced_health_service = None
            logger.info("Global enhanced health service shutdown completed")
        except Exception as e:
            logger.error("Error during enhanced health service shutdown", error=str(e))
            raise
    else:
        logger.debug("Enhanced health service already shutdown or never initialized")
