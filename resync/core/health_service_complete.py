from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Soft import for aiofiles (optional dependency)
try:
    import aiofiles  # type: ignore
except ImportError:
    aiofiles = None  # type: ignore
import psutil

from resync.core.app_context import AppContext
from resync.core.cache_hierarchy import get_cache_hierarchy
from resync.core.connection_pool_manager import get_connection_pool_manager
from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
)
from resync.core.tws_monitor import tws_monitor
from resync.core.websocket_pool_manager import websocket_pool_manager
from resync.settings import settings

from .health_utils import get_health_checks_dict, initialize_health_result

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Comprehensive health check service for all system components."""

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        self.config = config or HealthCheckConfig()
        self.health_history: List[HealthStatusHistory] = []
        self.last_health_check: Optional[datetime] = None
        self.component_cache: Dict[str, ComponentHealth] = {}
        self.cache_expiry = timedelta(seconds=self.config.check_interval_seconds)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health check monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Health check monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while self._is_monitoring:
            try:
                await self.perform_comprehensive_health_check()
                await asyncio.sleep(self.config.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(10)  # Brief pause on error

    async def perform_comprehensive_health_check(self) -> HealthCheckResult:
        """Perform comprehensive health check on all system components."""
        start_time = time.time()
        correlation_id = AppContext.get_correlation_id()

        logger.debug(
            f"Starting comprehensive health check [correlation_id: {correlation_id}]"
        )

        # Initialize result
        result = initialize_health_result(correlation_id)

        # Perform all health checks in parallel
        health_checks = get_health_checks_dict(self)

        # Execute all checks
        check_results = await asyncio.gather(
            *health_checks.values(), return_exceptions=True
        )

        # Process results
        for component_name, check_result in zip(health_checks.keys(), check_results):
            if isinstance(check_result, Exception):
                # Handle check failure
                logger.error(
                    f"Health check failed for {component_name}: {check_result}"
                )
                component_health = ComponentHealth(
                    name=component_name,
                    component_type=self._get_component_type(component_name),
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(check_result.__class__.__name__)} - {str(check_result)}",
                    last_check=datetime.now(),
                )
            else:
                component_health = check_result

            result.components[component_name] = component_health

        # Determine overall status
        result.overall_status = self._calculate_overall_status(result.components)

        # Generate summary
        result.summary = self._generate_summary(result.components)

        # Check for alerts
        if self.config.alert_enabled:
            result.alerts = self._check_alerts(result.components)

        # Record performance metrics
        result.performance_metrics = {
            "total_check_time_ms": (time.time() - start_time) * 1000,
            "components_checked": len(result.components),
            "timestamp": time.time(),
        }

        # Update history
        self._update_health_history(result)

        self.last_health_check = datetime.now()
        self.component_cache = result.components.copy()

        logger.debug(
            f"Health check completed in {result.performance_metrics['total_check_time_ms']:.2f}ms"
        )

        return result

    async def _check_database_health(self) -> ComponentHealth:
        """Check database health for PostgreSQL/MySQL/SQLite."""
        start_time = time.time()

        try:
            # Get connection pool manager
            pool_manager = await get_connection_pool_manager()
            database_pool = pool_manager.get_pool("database")

            if not database_pool:
                return ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNKNOWN,
                    message="Database connection pool not available",
                    last_check=datetime.now(),
                )

            # Perform health check
            is_healthy = await database_pool.health_check()
            stats = database_pool.get_stats()
            response_time = (time.time() - start_time) * 1000

            if is_healthy:
                status = HealthStatus.HEALTHY
                message = f"Database connection healthy (active: {stats.active_connections}, idle: {stats.idle_connections})"
            else:
                status = HealthStatus.UNHEALTHY
                message = (
                    f"Database connection failed (errors: {stats.connection_errors})"
                )

            return ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "active_connections": stats.active_connections,
                    "idle_connections": stats.idle_connections,
                    "total_connections": stats.total_connections,
                    "connection_errors": stats.connection_errors,
                    "pool_hits": stats.pool_hits,
                    "pool_misses": stats.pool_misses,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_redis_health(self) -> ComponentHealth:
        """Check Redis health and connectivity."""
        start_time = time.time()

        try:
            # Get connection pool manager
            pool_manager = await get_connection_pool_manager()
            redis_pool = pool_manager.get_pool("redis")

            if not redis_pool:
                return ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.UNKNOWN,
                    message="Redis connection pool not available",
                    last_check=datetime.now(),
                )

            # Perform health check
            is_healthy = await redis_pool.health_check()
            stats = redis_pool.get_stats()
            response_time = (time.time() - start_time) * 1000

            if is_healthy:
                status = HealthStatus.HEALTHY
                message = (
                    f"Redis connection healthy (connected: {stats.active_connections})"
                )
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Redis connection failed (errors: {stats.connection_errors})"

            return ComponentHealth(
                name="redis",
                component_type=ComponentType.REDIS,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "active_connections": stats.active_connections,
                    "idle_connections": stats.idle_connections,
                    "total_connections": stats.total_connections,
                    "connection_errors": stats.connection_errors,
                    "last_health_check": (
                        stats.last_health_check.isoformat()
                        if stats.last_health_check
                        else None
                    ),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="redis",
                component_type=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cache_health(self) -> ComponentHealth:
        """Check cache hierarchy health."""
        start_time = time.time()

        try:
            cache_hierarchy = get_cache_hierarchy()

            if not cache_hierarchy.is_running:
                return ComponentHealth(
                    name="cache_hierarchy",
                    component_type=ComponentType.CACHE,
                    status=HealthStatus.DEGRADED,
                    message="Cache hierarchy is not running",
                    last_check=datetime.now(),
                )

            # Get cache metrics
            metrics = cache_hierarchy.get_metrics()
            l1_size, l2_size = cache_hierarchy.size()
            response_time = (time.time() - start_time) * 1000

            # Determine status based on hit ratios
            if metrics["overall_hit_ratio"] < 0.5:  # Less than 50% hit ratio
                status = HealthStatus.DEGRADED
                message = f"Low cache hit ratio: {metrics['overall_hit_ratio']:.2%}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Cache operating normally (L1: {l1_size}, L2: {l2_size})"

            return ComponentHealth(
                name="cache_hierarchy",
                component_type=ComponentType.CACHE,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "l1_cache_size": l1_size,
                    "l2_cache_size": l2_size,
                    "l1_hit_ratio": metrics["l1_hit_ratio"],
                    "l2_hit_ratio": metrics["l2_hit_ratio"],
                    "overall_hit_ratio": metrics["overall_hit_ratio"],
                    "total_gets": metrics["total_gets"],
                    "total_sets": metrics["total_sets"],
                    "l1_evictions": metrics["l1_evictions"],
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="cache_hierarchy",
                component_type=ComponentType.CACHE,
                status=HealthStatus.UNHEALTHY,
                message=f"Cache health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_file_system_health(self) -> ComponentHealth:
        """Check file system health and disk space."""
        start_time = time.time()

        try:
            # Check disk usage
            disk_usage = psutil.disk_usage("/")
            disk_percent = (disk_usage.used / disk_usage.total) * 100

            # Check critical directories
            critical_dirs = [
                settings.BASE_DIR,
                settings.BASE_DIR / "logs",
                (
                    settings.BASE_DIR / "temp"
                    if hasattr(settings, "TEMP_DIR")
                    else Path("/tmp")
                ),
            ]

            dir_statuses = {}
            for dir_path in critical_dirs:
                if dir_path.exists():
                    try:
                        # Test write access
                        test_file = dir_path / ".health_check_test"
                        if aiofiles is None:
                            dir_statuses[
                                str(dir_path)
                            ] = "skipped (aiofiles not available)"
                        else:
                            async with aiofiles.open(test_file, "w") as f:
                                await f.write("health check test")
                            await aiofiles.os.remove(test_file)
                            dir_statuses[str(dir_path)] = "accessible"
                    except Exception as e:
                        dir_statuses[str(dir_path)] = f"error: {str(e)}"
                else:
                    dir_statuses[str(dir_path)] = "not_found"

            response_time = (time.time() - start_time) * 1000

            # Determine status
            if disk_percent > self.config.file_system_threshold_percent:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {disk_percent:.1f}%"
            elif any("error" in status for status in dir_statuses.values()):
                status = HealthStatus.DEGRADED
                message = "Some directories are not accessible"
            else:
                status = HealthStatus.HEALTHY
                message = f"File system healthy ({disk_percent:.1f}% disk usage)"

            return ComponentHealth(
                name="file_system",
                component_type=ComponentType.FILE_SYSTEM,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "disk_usage_percent": disk_percent,
                    "disk_free_gb": disk_usage.free / (1024**3),
                    "disk_total_gb": disk_usage.total / (1024**3),
                    "directory_statuses": dir_statuses,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="file_system",
                component_type=ComponentType.FILE_SYSTEM,
                status=HealthStatus.UNHEALTHY,
                message=f"File system health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_memory_health(self) -> ComponentHealth:
        """Check memory usage."""
        start_time = time.time()

        try:
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Get process-specific memory usage
            process = psutil.Process()
            process_memory_mb = process.memory_info().rss / (1024 * 1024)

            response_time = (time.time() - start_time) * 1000

            # Determine status
            if memory_percent > self.config.memory_threshold_percent:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}%"

            return ComponentHealth(
                name="memory",
                component_type=ComponentType.MEMORY,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "memory_usage_percent": memory_percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "process_memory_mb": process_memory_mb,
                    "swap_usage_percent": (
                        psutil.swap_memory().percent
                        if hasattr(psutil, "swap_memory")
                        else 0
                    ),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="memory",
                component_type=ComponentType.MEMORY,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cpu_health(self) -> ComponentHealth:
        """Check CPU load."""
        start_time = time.time()

        try:
            # Get CPU usage (non-blocking, 1-second interval)
            cpu_percent = psutil.cpu_percent(interval=1)

            # Get CPU count
            cpu_count = psutil.cpu_count()

            # Get load average (Unix-like systems)
            load_avg = None
            if hasattr(psutil, "getloadavg"):
                load_avg = psutil.getloadavg()

            response_time = (time.time() - start_time) * 1000

            # Determine status
            if cpu_percent > self.config.cpu_threshold_percent:
                status = HealthStatus.DEGRADED
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            return ComponentHealth(
                name="cpu",
                component_type=ComponentType.CPU,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "cpu_usage_percent": cpu_percent,
                    "cpu_count": cpu_count,
                    "load_average": load_avg,
                    "cpu_frequency_mhz": (
                        psutil.cpu_freq().current if psutil.cpu_freq() else None
                    ),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="cpu",
                component_type=ComponentType.CPU,
                status=HealthStatus.UNHEALTHY,
                message=f"CPU health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_tws_monitor_health(self) -> ComponentHealth:
        """Check TWS monitor health."""
        start_time = time.time()

        try:
            # Get current metrics from TWS monitor
            metrics = tws_monitor.get_current_metrics()
            # alerts = tws_monitor.get_alerts(limit=5)  # Removed unused variable
            response_time = (time.time() - start_time) * 1000

            # Determine status based on metrics
            if metrics["circuit_breaker_state"] == "open":
                status = HealthStatus.UNHEALTHY
                message = "TWS circuit breaker is open"
            elif metrics["connection_status"] == "down":
                status = HealthStatus.UNHEALTHY
                message = "TWS connection is down"
            else:
                status = HealthStatus.HEALTHY
                message = "TWS monitor operational"

            return ComponentHealth(
                name="tws_monitor",
                component_type=ComponentType.TWS,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "connection_status": metrics["connection_status"],
                    "circuit_breaker_state": metrics["circuit_breaker_state"],
                    "active_connections": metrics["active_connections"],
                    "connection_errors": metrics["connection_errors"],
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="tws_monitor",
                component_type=ComponentType.TWS,
                status=HealthStatus.UNHEALTHY,
                message=f"TWS monitor health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_connection_pools_health(self) -> ComponentHealth:
        """Check connection pools health."""
        start_time = time.time()

        try:
            # Get connection pool manager
            pool_manager = await get_connection_pool_manager()
            pools = pool_manager.get_all_pools()

            # Check each pool
            pool_statuses = {}
            for pool_name, pool in pools.items():
                is_healthy = await pool.health_check()
                stats = pool.get_stats()
                pool_statuses[pool_name] = {
                    "healthy": is_healthy,
                    "active_connections": stats.active_connections,
                    "idle_connections": stats.idle_connections,
                    "total_connections": stats.total_connections,
                    "connection_errors": stats.connection_errors,
                    "pool_hits": stats.pool_hits,
                    "pool_misses": stats.pool_misses,
                }

            # Determine overall status
            all_healthy = all(status["healthy"] for status in pool_statuses.values())
            if all_healthy:
                status = HealthStatus.HEALTHY
                message = "All connection pools healthy"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Some connection pools unhealthy"

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="connection_pools",
                component_type=ComponentType.CONNECTION_POOL,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={"pools": pool_statuses},
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="connection_pools",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection pools health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_websocket_pool_health(self) -> ComponentHealth:
        """Check WebSocket pool health."""
        start_time = time.time()

        try:
            # Get WebSocket pool manager
            pool_manager = websocket_pool_manager
            stats = pool_manager.get_stats()

            # Determine status
            if stats.active_connections > 0:
                status = HealthStatus.HEALTHY
                message = f"WebSocket pool healthy ({stats.active_connections} active connections)"
            else:
                status = HealthStatus.DEGRADED
                message = "WebSocket pool has no active connections"

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="websocket_pool",
                component_type=ComponentType.WEBSOCKET_POOL,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "active_connections": stats.active_connections,
                    "idle_connections": stats.idle_connections,
                    "total_connections": stats.total_connections,
                    "connection_errors": stats.connection_errors,
                    "last_health_check": (
                        stats.last_health_check.isoformat()
                        if stats.last_health_check
                        else None
                    ),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="websocket_pool",
                component_type=ComponentType.WEBSOCKET_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"WebSocket pool health check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    def _get_component_type(self, component_name: str) -> ComponentType:
        """Map component name to component type."""
        component_type_map = {
            "database": ComponentType.DATABASE,
            "redis": ComponentType.REDIS,
            "cache_hierarchy": ComponentType.CACHE,
            "file_system": ComponentType.FILE_SYSTEM,
            "memory": ComponentType.MEMORY,
            "cpu": ComponentType.CPU,
            "tws_monitor": ComponentType.TWS,
            "connection_pools": ComponentType.CONNECTION_POOL,
            "websocket_pool": ComponentType.WEBSOCKET_POOL,
        }
        return component_type_map.get(component_name, ComponentType.OTHER)

    def _calculate_overall_status(
        self, components: Dict[str, ComponentHealth]
    ) -> HealthStatus:
        """Calculate overall health status based on component statuses."""
        if not components:
            return HealthStatus.UNKNOWN

        # If any critical component is unhealthy, overall is unhealthy
        critical_components = ["database", "redis", "tws_monitor"]
        for comp_name in critical_components:
            if (
                comp_name in components
                and components[comp_name].status == HealthStatus.UNHEALTHY
            ):
                return HealthStatus.UNHEALTHY

        # If any component is degraded, overall is degraded
        for comp in components.values():
            if comp.status == HealthStatus.DEGRADED:
                return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _generate_summary(
        self, components: Dict[str, ComponentHealth]
    ) -> Dict[str, str]:
        """Generate health summary."""
        summary = {}
        for comp_name, comp in components.items():
            summary[comp_name] = f"{comp.status.name}: {comp.message}"
        return summary

    def _check_alerts(self, components: Dict[str, ComponentHealth]) -> List[str]:
        """Check for health alerts based on component statuses."""
        alerts = []
        for comp_name, comp in components.items():
            if comp.status == HealthStatus.DEGRADED:
                alerts.append(f"{comp_name} is degraded: {comp.message}")
            elif comp.status == HealthStatus.UNHEALTHY:
                alerts.append(f"{comp_name} is unhealthy: {comp.message}")
        return alerts

    def _update_health_history(self, result: HealthCheckResult) -> None:
        """Update health check history."""
        self.health_history.append(
            HealthStatusHistory(
                timestamp=result.timestamp,
                overall_status=result.overall_status,
                components={
                    name: comp.status for name, comp in result.components.items()
                },
            )
        )
