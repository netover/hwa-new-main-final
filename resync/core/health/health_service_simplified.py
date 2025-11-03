"""
Simplified Health Service

This module provides a simplified health check service that maintains API compatibility
while reducing complexity and resource usage. It runs minimal checks every 300 seconds
and uses only essential Prometheus metrics with low cardinality.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime

import psutil
import structlog
from resync.core.websocket_pool_manager import get_websocket_pool_manager
from resync.config.settings import get_settings
from resync.core.cache import get_cache_hierarchy
from resync.core.connection_pool_manager import (
    get_advanced_connection_pool_manager,
)
from resync.models.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckResult,
    HealthStatus,
    SystemHealthStatus,
)

# Import simplified metrics
from .health_metrics_simplified import (
    get_health_metrics,
    record_health_check_with_timing,
)

logger = structlog.get_logger(__name__)


class SimplifiedHealthService:
    """
    Simplified health check service with minimal resource usage.

    This service provides:
    - Basic health checks for core components
    - Background monitoring every 300 seconds (configurable)
    - Minimal Prometheus metrics with low cardinality
    - No circuit breakers or thread pools (pure asyncio)
    - API compatibility with existing health endpoints
    """

    def __init__(self):
        """Initialize simplified health service."""
        self.settings = get_settings()
        self._component_cache: dict[str, ComponentHealth] = {}
        self._last_system_check: datetime | None = None
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False
        self._check_interval = self.settings.health_check_interval_seconds

        # Semaphore to limit concurrent checks
        self._check_semaphore = asyncio.Semaphore(5)

    async def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(
            "simplified_health_monitoring_started",
            interval_seconds=self._check_interval,
        )

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task
        logger.info("simplified_health_monitoring_stopped")

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """
        Run health checks on all system components.

        Returns:
            List[HealthCheckResult]: List of health check results for all components
        """
        start_time = time.time()
        results = []

        # Define minimal set of components to check
        components_to_check = [
            "database",
            "redis",
            "cache_hierarchy",
            "system_resources",
            "websocket_pool",
        ]

        # Create tasks for all checks with timeouts
        tasks = []
        for component_name in components_to_check:
            task = asyncio.create_task(
                self._check_component_with_timeout(component_name)
            )
            tasks.append(task)

        # Wait for all checks to complete with exception handling
        component_results = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Process results
        for component_name, result in zip(
            components_to_check, component_results, strict=False
        ):
            if isinstance(result, Exception):
                # Create error result for failed checks
                error_health = ComponentHealth(
                    name=component_name,
                    component_type=self._get_component_type(component_name),
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(result)}",
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
            else:
                results.append(result)

        # Update cache with latest results
        for result in results:
            for name, health in result.components.items():
                self._component_cache[name] = health

        self._last_system_check = datetime.now()

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            "health_checks_completed",
            component_count=len(components_to_check),
            elapsed_ms=elapsed_ms,
        )

        return results

    async def get_component_health(
        self, component_type: ComponentType
    ) -> ComponentHealth:
        """
        Get health status for a specific component type.

        Args:
            component_type: The type of component to check

        Returns:
            ComponentHealth: Health status of component

        Raises:
            ValueError: If component type is not supported
        """
        # Map component type to component name
        component_name_map = {
            ComponentType.DATABASE: "database",
            ComponentType.REDIS: "redis",
            ComponentType.CACHE: "cache_hierarchy",
            ComponentType.FILE_SYSTEM: "system_resources",
            ComponentType.MEMORY: "system_resources",
            ComponentType.CPU: "system_resources",
            ComponentType.WEBSOCKET: "websocket_pool",
        }

        component_name = component_name_map.get(component_type)
        if not component_name:
            raise ValueError(f"Unsupported component type: {component_type}")

        # Check cache first (5 minutes expiry)
        cached_health = self._component_cache.get(component_name)
        if cached_health:
            age = datetime.now() - cached_health.last_check
            if age.total_seconds() < 300:
                return cached_health

        # Perform fresh health check
        _, result = await self._check_component_with_timeout(component_name)

        # Update cache
        for name, health in result.components.items():
            self._component_cache[name] = health
            return health

        # Fallback to unknown status
        return ComponentHealth(
            name=component_name,
            component_type=component_type,
            status=HealthStatus.UNKNOWN,
            message="Component health check failed",
            last_check=datetime.now(),
        )

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
                critical_count / total_components
                if total_components > 0
                else 0
            )

            if critical_ratio > 0.5:  # More than 50% critical
                return SystemHealthStatus.CRITICAL
            if warning_count > 0 or critical_count > 0:
                return SystemHealthStatus.WARNING
            return SystemHealthStatus.OK

        except (RuntimeError, ConnectionError, ImportError):
            # Return critical status on any error
            return SystemHealthStatus.CRITICAL

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._is_monitoring:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except (ConnectionError, RuntimeError) as e:
                logger.error(
                    "health_monitoring_error",
                    error=str(e),
                    exc_info=True,
                )
                # Continue monitoring despite errors
                await asyncio.sleep(min(60, self._check_interval))

    async def _check_component_with_timeout(
        self, component_name: str
    ) -> tuple[str, HealthCheckResult]:
        """
        Check a single component with timeout.

        Args:
            component_name: Name of component to check

        Returns:
            Tuple of component name and health check result
        """
        async with self._check_semaphore:
            try:
                # Use asyncio.wait_for for timeout
                component_type = self._get_component_type(component_name)
                health = await asyncio.wait_for(
                    self._perform_basic_health_check(
                        component_name, component_type
                    ),
                    timeout=2.0,  # 2 second timeout per check
                )

                # Record metrics
                record_health_check_with_timing(component_name, health.status)

                # Create result
                result = HealthCheckResult(
                    overall_status=health.status,
                    timestamp=datetime.now(),
                    correlation_id=f"health_check_{component_name}_{int(time.time())}",
                    components={component_name: health},
                    summary={
                        "total_components": 1,
                        "healthy": (
                            1 if health.status == HealthStatus.HEALTHY else 0
                        ),
                        "degraded": (
                            1 if health.status == HealthStatus.DEGRADED else 0
                        ),
                        "unhealthy": (
                            1 if health.status == HealthStatus.UNHEALTHY else 0
                        ),
                        "unknown": (
                            1 if health.status == HealthStatus.UNKNOWN else 0
                        ),
                    },
                )

                return component_name, result

            except asyncio.TimeoutError:
                # Create timeout result
                timeout_health = ComponentHealth(
                    name=component_name,
                    component_type=self._get_component_type(component_name),
                    status=HealthStatus.UNHEALTHY,
                    message="Health check timed out",
                    last_check=datetime.now(),
                    error_count=1,
                )

                # Record metrics for timeout
                record_health_check_with_timing(
                    component_name, timeout_health.status
                )

                timeout_result = HealthCheckResult(
                    overall_status=HealthStatus.UNHEALTHY,
                    timestamp=datetime.now(),
                    correlation_id=f"health_check_{component_name}_timeout_{int(time.time())}",
                    components={component_name: timeout_health},
                    summary={"total_components": 1, "unhealthy": 1},
                )

                return component_name, timeout_result
            except (ImportError, AttributeError, ConnectionError):
                # Create error result for failed checks
                error_health = ComponentHealth(
                    name=component_name,
                    component_type=self._get_component_type(component_name),
                    status=HealthStatus.UNKNOWN,
                    message="Health check failed",
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

                return component_name, error_result

    async def _perform_basic_health_check(
        self, component_name: str, component_type: ComponentType
    ) -> ComponentHealth:
        """
        Perform a basic health check for a component.

        Args:
            component_name: Name of component
            component_type: Type of component

        Returns:
            ComponentHealth: Health status of component
        """
        start_time = time.time()

        try:
            # Use a dictionary to map component types to their check functions
            check_map = {
                ComponentType.DATABASE: self._check_database_health_basic,
                ComponentType.REDIS: self._check_redis_health_basic,
                ComponentType.CACHE: self._check_cache_health_basic,
                ComponentType.WEBSOCKET: self._check_websocket_pool_health_basic,
            }

            # Check if component type has a specific check function
            if component_type in check_map:
                return await check_map[component_type](component_name)

            # Handle system resource components
            if component_type in [
                ComponentType.FILE_SYSTEM,
                ComponentType.MEMORY,
                ComponentType.CPU,
            ]:
                return await self._check_system_resources_health_basic(
                    component_name
                )

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

        except (ImportError, AttributeError, ConnectionError) as e:
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
        """Basic database health check via connection pool manager."""
        try:
            pool_manager = await get_advanced_connection_pool_manager()
            db_pool = pool_manager.get_db_pool()

            # Check pool health
            pool_stats = db_pool.get_stats()
            active_connections = pool_stats.get("active_connections", 0)
            total_connections = pool_stats.get("total_connections", 0)

            # Simple health check - if we have connections, assume healthy
            if total_connections > 0:
                return ComponentHealth(
                    name=component_name,
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.HEALTHY,
                    message=(
                        f"Database pool healthy "
                        f"({active_connections}/{total_connections} active)"
                    ),
                    response_time_ms=10.0,
                    last_check=datetime.now(),
                    metadata={
                        "active_connections": active_connections,
                        "total_connections": total_connections,
                    },
                )
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message="No database connections available",
                response_time_ms=10.0,
                last_check=datetime.now(),
                error_count=1,
            )
        except (ImportError, AttributeError, ConnectionError) as e:
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNKNOWN,
                message=f"Database health check failed: {str(e)}",
                response_time_ms=10.0,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_redis_health_basic(
        self, component_name: str
    ) -> ComponentHealth:
        """Basic Redis health check via connection pool manager."""
        try:
            pool_manager = await get_advanced_connection_pool_manager()
            redis_pool = pool_manager.get_redis_pool()

            # Check pool health
            pool_stats = redis_pool.get_stats()
            active_connections = pool_stats.get("active_connections", 0)
            total_connections = pool_stats.get("total_connections", 0)

            # Simple health check - if we have connections, assume healthy
            if total_connections > 0:
                return ComponentHealth(
                    name=component_name,
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.HEALTHY,
                    message=f"Redis pool healthy ({active_connections}/{total_connections} active)",
                    response_time_ms=5.0,
                    last_check=datetime.now(),
                    metadata={
                        "active_connections": active_connections,
                        "total_connections": total_connections,
                    },
                )
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message="No Redis connections available",
                response_time_ms=5.0,
                last_check=datetime.now(),
                error_count=1,
            )
        except (ImportError, AttributeError, ConnectionError) as e:
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.REDIS,
                status=HealthStatus.UNKNOWN,
                message=f"Redis health check failed: {str(e)}",
                response_time_ms=5.0,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cache_health_basic(
        self, component_name: str
    ) -> ComponentHealth:
        """Basic cache health check."""
        try:
            cache = get_cache_hierarchy()

            # Get basic cache stats - handle different cache implementations
            try:
                stats = cache.get_stats()
                l1_size = stats.get("l1_size", 0)
                l2_size = stats.get("l2_size", 0)
                hit_ratio = stats.get("hit_ratio", 0.0)
            except AttributeError:
                # Fallback for cache implementations without get_stats
                l1_size = 0
                l2_size = 0
                hit_ratio = 0.0

            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.CACHE,
                status=HealthStatus.HEALTHY,
                message=f"Cache healthy (L1: {l1_size}, L2: {l2_size}, Hit ratio: {hit_ratio:.1%})",
                response_time_ms=2.0,
                last_check=datetime.now(),
                metadata={
                    "l1_size": l1_size,
                    "l2_size": l2_size,
                    "hit_ratio": hit_ratio,
                },
            )
        except (ImportError, AttributeError, ConnectionError) as e:
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.CACHE,
                status=HealthStatus.UNKNOWN,
                message=f"Cache health check failed: {str(e)}",
                response_time_ms=2.0,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_system_resources_health_basic(
        self, component_name: str
    ) -> ComponentHealth:
        """Basic system resources health check."""
        try:
            # Get basic system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Determine status based on thresholds
            status = HealthStatus.HEALTHY
            message_parts = []

            if cpu_percent > 90:
                status = HealthStatus.DEGRADED
                message_parts.append(f"High CPU: {cpu_percent:.1f}%")
            elif cpu_percent > 95:
                status = HealthStatus.UNHEALTHY
                message_parts.append(f"Critical CPU: {cpu_percent:.1f}%")
            else:
                message_parts.append(f"CPU: {cpu_percent:.1f}%")

            if memory.percent > 85:
                if status != HealthStatus.UNHEALTHY:
                    status = HealthStatus.DEGRADED
                message_parts.append(f"High memory: {memory.percent:.1f}%")
            elif memory.percent > 95:
                status = HealthStatus.UNHEALTHY
                message_parts.append(f"Critical memory: {memory.percent:.1f}%")
            else:
                message_parts.append(f"Memory: {memory.percent:.1f}%")

            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 90:
                if status != HealthStatus.UNHEALTHY:
                    status = HealthStatus.DEGRADED
                message_parts.append(f"High disk: {disk_percent:.1f}%")
            elif disk_percent > 95:
                status = HealthStatus.UNHEALTHY
                message_parts.append(f"Critical disk: {disk_percent:.1f}%")
            else:
                message_parts.append(f"Disk: {disk_percent:.1f}%")

            message = "System resources: " + ", ".join(message_parts)

            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.OTHER,
                status=status,
                message=message,
                response_time_ms=1.0,
                last_check=datetime.now(),
                metadata={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk_percent,
                },
            )
        except (ImportError, AttributeError, ConnectionError) as e:
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.OTHER,
                status=HealthStatus.UNKNOWN,
                message=f"System resources check failed: {str(e)}",
                response_time_ms=1.0,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_websocket_pool_health_basic(
        self, component_name: str
    ) -> ComponentHealth:
        """Basic websocket pool health check."""
        try:
            pool_manager = get_websocket_pool_manager()

            # Get basic pool stats - handle different pool implementations
            try:
                stats = pool_manager.get_stats()
                active_connections = stats.get("active_connections", 0)
                total_connections = stats.get("total_connections", 0)
            except AttributeError:
                # Fallback for pool implementations without get_stats
                active_connections = 0
                total_connections = 0

            # Simple health check - if pool manager exists, assume healthy
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.WEBSOCKET,
                status=HealthStatus.HEALTHY,
                message=f"WebSocket pool healthy ({active_connections}/{total_connections} active)",
                response_time_ms=1.0,
                last_check=datetime.now(),
                metadata={
                    "active_connections": active_connections,
                    "total_connections": total_connections,
                },
            )
        except (ImportError, AttributeError, ConnectionError):
            # If websocket pool is not available, mark as unknown/disabled
            return ComponentHealth(
                name=component_name,
                component_type=ComponentType.WEBSOCKET,
                status=HealthStatus.UNKNOWN,
                message="WebSocket pool not available or disabled",
                response_time_ms=1.0,
                last_check=datetime.now(),
            )

    def get_prometheus_metrics(self) -> tuple[str, str]:
        """
        Get Prometheus metrics for health checks.

        Returns:
            Tuple of (metrics_content, content_type)
        """
        metrics = get_health_metrics()
        return metrics.get_metrics(), metrics.get_content_type()

    def _get_component_type(self, name: str) -> ComponentType:
        """Map component name to component type."""
        mapping = {
            "database": ComponentType.DATABASE,
            "redis": ComponentType.REDIS,
            "cache_hierarchy": ComponentType.CACHE,
            "system_resources": ComponentType.OTHER,
            "websocket_pool": ComponentType.WEBSOCKET,
        }
        return mapping.get(name, ComponentType.OTHER)




