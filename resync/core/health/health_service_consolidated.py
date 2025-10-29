"""
Consolidated Health Service

This module provides a consolidated health check service that combines simplicity
of simplified implementation with critical features from the full implementation.
It maintains API compatibility while reducing complexity and resource usage.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime, timedelta
from typing import Any

import psutil
import structlog
from resync_new.models.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
    SystemHealthStatus,
)

# Import simplified metrics
from .health_metrics_simplified import (
    get_health_metrics,
    record_health_check_with_timing,
)

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Simple circuit breaker implementation for health checks."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self._last_check = datetime.now()

    async def call(self, func, *args, **kwargs):
        """Executes function with circuit breaker protection."""
        if self.state == "open":
            # Check if it's time to attempt recovery
            if (
                datetime.now() - self.last_failure_time
            ).seconds > self.recovery_timeout:
                self.state = "half-open"
            else:
                # Circuit is open, fail fast
                raise Exception(
                    f"Circuit breaker is open for {self.recovery_timeout}s"
                )

        try:
            result = await func(*args, **kwargs)
            # On success, reset if we were in half-open state
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            # If we've exceeded threshold, open circuit
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    "circuit_breaker_opened", failure_count=self.failure_count
                )
            raise e


class ConsolidatedHealthService:
    """
    Consolidated health check service with optimal balance of features and simplicity.

    This service provides:
    - Basic health checks for core components
    - Background monitoring every 300 seconds (configurable)
    - Minimal Prometheus metrics with low cardinality
    - Circuit breaker protection for critical components
    - API compatibility with existing health endpoints
    - Component caching to reduce resource usage
    """

    def __init__(self, config: HealthCheckConfig | None = None):
        """Initialize consolidated health service."""
        self.config = config or HealthCheckConfig()
        self._component_cache: dict[str, ComponentHealth] = {}
        self._last_system_check: datetime | None = None
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False
        self._check_interval = 300  # Default 5 minutes
        self.health_history: list[HealthStatusHistory] = []
        self.last_health_check: datetime | None = None
        self.cache_expiry = timedelta(
            seconds=self.config.check_interval_seconds
        )

        # Semaphore to limit concurrent checks
        self._check_semaphore = asyncio.Semaphore(5)

        # Circuit breakers for critical components
        self._circuit_breakers = {
            "database": CircuitBreaker(),
            "redis": CircuitBreaker(),
            "cache": CircuitBreaker(),
            "websocket_pool": CircuitBreaker(),
        }

        # Locks for thread safety
        self._cache_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()

    async def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(
            "consolidated_health_monitoring_started",
            interval_seconds=self._check_interval,
        )

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task
        logger.info("consolidated_health_monitoring_stopped")

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """
        Run health checks on all system components.

        Returns:
            List[HealthCheckResult]: List of health check results for all components
        """
        start_time = time.time()
        results = []

        # Define components to check
        components_to_check = [
            "database",
            "redis",
            "cache_hierarchy",
            "system_resources",
            "websocket_pool",
        ]

        # Run checks with semaphore to limit concurrency
        async with self._check_semaphore:
            tasks = [
                self._check_component(component)
                for component in components_to_check
            ]
            check_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            # Process results
            for i, result in enumerate(check_results):
                component = components_to_check[i]
                if isinstance(result, Exception):
                    logger.error(
                        "health_check_failed",
                        component=component,
                        error=str(result),
                    )
                    results.append(
                        HealthCheckResult(
                            component=ComponentType(component),
                            status=HealthStatus.UNHEALTHY,
                            message=f"Health check failed: {str(result)}",
                            timestamp=datetime.now(),
                            response_time_ms=0,
                        )
                    )
                else:
                    results.append(result)

        # Record metrics
        total_time_ms = (time.time() - start_time) * 1000
        record_health_check_with_timing("all_checks", total_time_ms)

        return results

    async def get_system_health(self) -> SystemHealthStatus:
        """
        Get overall system health status.

        Returns:
            SystemHealthStatus: Overall system health status
        """
        # If we have recent cached results, use them
        if (
            self._last_system_check
            and (datetime.now() - self._last_system_check).seconds < 60
        ):
            return self._get_cached_system_health()

        # Run all checks
        results = await self.run_all_checks()
        self._last_system_check = datetime.now()

        # Determine overall status
        unhealthy_count = sum(
            1 for result in results if result.status == HealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1 for result in results if result.status == HealthStatus.DEGRADED
        )

        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        # Create system health status
        system_health = SystemHealthStatus(
            status=overall_status,
            timestamp=datetime.now(),
            components={result.component.value: result for result in results},
            total_components=len(results),
            healthy_components=len(results) - unhealthy_count - degraded_count,
            unhealthy_components=unhealthy_count,
            degraded_components=degraded_count,
        )

        # Cache result
        await self._cache_system_health(system_health)

        return system_health

    async def get_component_health(self, component: str) -> HealthCheckResult:
        """
        Get health status for a specific component.

        Args:
            component: Component name to check

        Returns:
            HealthCheckResult: Health check result for component
        """
        return await self._check_component(component)

    async def _check_component(self, component: str) -> HealthCheckResult:
        """Check health of a specific component."""
        start_time = time.time()

        try:
            # Get circuit breaker for this component
            circuit_breaker = self._circuit_breakers.get(component)

            # Define check function based on component
            if component == "database":
                check_func = self._check_database_health
            elif component == "redis":
                check_func = self._check_redis_health
            elif component == "cache_hierarchy":
                check_func = self._check_cache_health
            elif component == "system_resources":
                check_func = self._check_system_resources_health
            elif component == "websocket_pool":
                check_func = self._check_websocket_pool_health
            else:
                return HealthCheckResult(
                    component=ComponentType(component),
                    status=HealthStatus.UNKNOWN,
                    message=f"Unknown component: {component}",
                    timestamp=datetime.now(),
                    response_time_ms=0,
                )

            # Run check with circuit breaker protection if available
            if circuit_breaker:
                result = await circuit_breaker.call(check_func)
            else:
                result = await check_func()

            # Record metrics
            response_time_ms = (time.time() - start_time) * 1000
            record_health_check_with_timing(component, response_time_ms)

            return result

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            logger.error(
                "component_health_check_failed",
                component=component,
                error=str(e),
                response_time_ms=response_time_ms,
            )
            return HealthCheckResult(
                component=ComponentType(component),
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=response_time_ms,
            )

    async def _check_database_health(self) -> HealthCheckResult:
        """Check database health."""
        try:
            # Simple database connectivity check
            # Try to import here to avoid circular dependencies
            from resync_new.core.connection_pool_manager import (
                get_advanced_connection_pool_manager,
            )

            connection_pool = get_advanced_connection_pool_manager()
            if connection_pool:
                # Check if we can get a connection
                pool_stats = connection_pool.get_pool_stats()
                if pool_stats.get("active_connections", 0) >= 0:
                    return HealthCheckResult(
                        component=ComponentType.DATABASE,
                        status=HealthStatus.HEALTHY,
                        message="Database connection pool is active",
                        timestamp=datetime.now(),
                        response_time_ms=0,
                    )

            return HealthCheckResult(
                component=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message="Database connection pool is not available",
                timestamp=datetime.now(),
                response_time_ms=0,
            )
        except Exception as e:
            return HealthCheckResult(
                component=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database health check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0,
            )

    async def _check_redis_health(self) -> HealthCheckResult:
        """Check Redis health."""
        try:
            # Simple Redis connectivity check
            # Try to import here to avoid circular dependencies
            from resync.core.cache.unified_cache import UnifiedAsyncCache

            cache = UnifiedAsyncCache.get_instance()
            if cache:
                # Try a simple ping operation
                await cache.ping()
                return HealthCheckResult(
                    component=ComponentType.REDIS,
                    status=HealthStatus.HEALTHY,
                    message="Redis is responding",
                    timestamp=datetime.now(),
                    response_time_ms=0,
                )

            return HealthCheckResult(
                component=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message="Redis cache is not available",
                timestamp=datetime.now(),
                response_time_ms=0,
            )
        except Exception as e:
            return HealthCheckResult(
                component=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis health check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0,
            )

    async def _check_cache_health(self) -> HealthCheckResult:
        """Check cache hierarchy health."""
        try:
            # Try to import here to avoid circular dependencies
            from resync.core.cache.unified_cache import UnifiedAsyncCache

            cache = UnifiedAsyncCache.get_instance()
            if cache:
                # Check cache statistics
                stats = await cache.get_stats()
                if stats:
                    return HealthCheckResult(
                        component=ComponentType.CACHE,
                        status=HealthStatus.HEALTHY,
                        message=f"Cache is operational: {stats}",
                        timestamp=datetime.now(),
                        response_time_ms=0,
                    )

            return HealthCheckResult(
                component=ComponentType.CACHE,
                status=HealthStatus.UNHEALTHY,
                message="Cache hierarchy is not available",
                timestamp=datetime.now(),
                response_time_ms=0,
            )
        except Exception as e:
            return HealthCheckResult(
                component=ComponentType.CACHE,
                status=HealthStatus.UNHEALTHY,
                message=f"Cache health check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0,
            )

    async def _check_system_resources_health(self) -> HealthCheckResult:
        """Check system resources health."""
        try:
            # Check CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Determine status based on thresholds
            cpu_status = HealthStatus.HEALTHY
            if cpu_percent > 90:
                cpu_status = HealthStatus.UNHEALTHY
            elif cpu_percent > 70:
                cpu_status = HealthStatus.DEGRADED

            memory_status = HealthStatus.HEALTHY
            if memory.percent > 90:
                memory_status = HealthStatus.UNHEALTHY
            elif memory.percent > 80:
                memory_status = HealthStatus.DEGRADED

            disk_status = HealthStatus.HEALTHY
            if disk.percent > 95:
                disk_status = HealthStatus.UNHEALTHY
            elif disk.percent > 85:
                disk_status = HealthStatus.DEGRADED

            # Overall status is the worst of all
            overall_status = HealthStatus.HEALTHY
            if (
                cpu_status == HealthStatus.UNHEALTHY
                or memory_status == HealthStatus.UNHEALTHY
                or disk_status == HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.UNHEALTHY
            elif (
                cpu_status == HealthStatus.DEGRADED
                or memory_status == HealthStatus.DEGRADED
                or disk_status == HealthStatus.DEGRADED
            ):
                overall_status = HealthStatus.DEGRADED

            message = (
                f"CPU: {cpu_percent:.1f}%, "
                f"Memory: {memory.percent:.1f}%, "
                f"Disk: {disk.percent:.1f}%"
            )

            return HealthCheckResult(
                component=ComponentType.SYSTEM_RESOURCES,
                status=overall_status,
                message=message,
                timestamp=datetime.now(),
                response_time_ms=0,
            )
        except Exception as e:
            return HealthCheckResult(
                component=ComponentType.SYSTEM_RESOURCES,
                status=HealthStatus.UNHEALTHY,
                message=f"System resources check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0,
            )

    async def _check_websocket_pool_health(self) -> HealthCheckResult:
        """Check WebSocket pool health."""
        try:
            # Try to import here to avoid circular dependencies
            from resync.core.websocket_pool_manager import (
                get_websocket_pool_manager,
            )

            websocket_pool = get_websocket_pool_manager()
            if websocket_pool:
                # Check pool statistics
                stats = websocket_pool.get_stats()
                if stats:
                    active_connections = stats.get("active_connections", 0)
                    return HealthCheckResult(
                        component=ComponentType.WEBSOCKET_POOL,
                        status=HealthStatus.HEALTHY,
                        message=f"WebSocket pool has {active_connections} active connections",
                        timestamp=datetime.now(),
                        response_time_ms=0,
                    )

            return HealthCheckResult(
                component=ComponentType.WEBSOCKET_POOL,
                status=HealthStatus.UNHEALTHY,
                message="WebSocket pool is not available",
                timestamp=datetime.now(),
                response_time_ms=0,
            )
        except Exception as e:
            return HealthCheckResult(
                component=ComponentType.WEBSOCKET_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"WebSocket pool check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0,
            )

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._is_monitoring:
            try:
                # Run health checks
                await self.run_all_checks()

                # Sleep until next check
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "monitoring_loop_error",
                    error=str(e),
                )
                # Sleep before retrying
                await asyncio.sleep(10)

    async def _cache_system_health(
        self, system_health: SystemHealthStatus
    ) -> None:
        """Cache system health result."""
        async with self._cache_lock:
            self._last_system_check = datetime.now()
            # Store in component cache for individual component checks
            for component, result in system_health.components.items():
                self._component_cache[component] = ComponentHealth(
                    component=ComponentType(component),
                    status=result.status,
                    last_check=result.timestamp,
                    message=result.message,
                )

    def _get_cached_system_health(self) -> SystemHealthStatus:
        """Get cached system health."""
        components = {}
        for component, health in self._component_cache.items():
            components[component] = HealthCheckResult(
                component=health.component,
                status=health.status,
                message=health.message,
                timestamp=health.last_check,
                response_time_ms=0,
            )

        # Determine overall status
        unhealthy_count = sum(
            1
            for result in components.values()
            if result.status == HealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1
            for result in components.values()
            if result.status == HealthStatus.DEGRADED
        )

        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return SystemHealthStatus(
            status=overall_status,
            timestamp=self._last_system_check or datetime.now(),
            components=components,
            total_components=len(components),
            healthy_components=len(components)
            - unhealthy_count
            - degraded_count,
            unhealthy_components=unhealthy_count,
            degraded_components=degraded_count,
        )

    async def get_health_metrics(self) -> dict[str, Any]:
        """Get health check metrics."""
        return get_health_metrics()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        async with self._cleanup_lock:
            await self.stop_monitoring()
            self._component_cache.clear()
            logger.info("consolidated_health_service_cleaned_up")


# Global service instance
_consolidated_health_service: ConsolidatedHealthService | None = None
_health_service_lock = asyncio.Lock()


async def get_consolidated_health_service() -> ConsolidatedHealthService:
    """
    Get the global consolidated health service instance.

    Returns:
        ConsolidatedHealthService: The global health service instance
    """
    global _consolidated_health_service

    if _consolidated_health_service is None:
        async with _health_service_lock:
            if _consolidated_health_service is None:
                _consolidated_health_service = ConsolidatedHealthService()
                await _consolidated_health_service.start_monitoring()
                logger.info("Consolidated health service initialized")

    return _consolidated_health_service


async def shutdown_consolidated_health_service() -> None:
    """Shutdown the global consolidated health service."""
    global _consolidated_health_service

    if _consolidated_health_service:
        await _consolidated_health_service.cleanup()
        _consolidated_health_service = None
        logger.info("Consolidated health service shutdown")
