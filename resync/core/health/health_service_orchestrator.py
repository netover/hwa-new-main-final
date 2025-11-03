"""
Health Service Orchestrator

This module provides the main coordination logic for health checks,
integrating various health monitoring components into a unified service.
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

logger = structlog.get_logger(__name__)


class HealthServiceOrchestrator:
    """
    Orchestrates health check operations and coordinates various health monitoring components.

    This class provides the main coordination logic for:
    - Executing comprehensive health checks
    - Managing component health results
    - Coordinating with various health monitoring subsystems
    - Providing a unified health check interface
    """

    def __init__(self, config: HealthCheckConfig | None = None):
        """
        Initialize the health service orchestrator.

        Args:
            config: Health check configuration (uses default if None)
        """
        self.config = config or HealthCheckConfig()
        self.last_health_check: datetime | None = None
        self._component_results: dict[str, ComponentHealth] = {}
        self._lock = asyncio.Lock()

    async def perform_comprehensive_health_check(
        self,
        proactive_monitor: Any | None = None,
        performance_collector: Any | None = None,
        cache_manager: Any | None = None,
    ) -> HealthCheckResult:
        """
        Perform comprehensive health check with coordination of all subsystems.

        Args:
            proactive_monitor: Proactive monitoring component
            performance_collector: Performance metrics collector
            cache_manager: Component cache manager

        Returns:
            Comprehensive health check result
        """
        start_time = time.time()
        correlation_id = f"health_{int(start_time)}"

        logger.debug(
            "starting_comprehensive_health_check",
            correlation_id=correlation_id,
        )

        # Initialize result with enhanced metadata
        from resync.core.health_utils import initialize_health_result

        result = initialize_health_result(correlation_id)

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

        # Perform all health checks in parallel
        health_checks = await self._get_health_checks_dict()

        # Execute all checks with timeout protection
        try:
            check_results = await asyncio.wait_for(
                asyncio.gather(
                    *health_checks.values(), return_exceptions=True
                ),
                timeout=30.0,  # 30 second global timeout
            )
        except asyncio.TimeoutError:
            # Handle timeout by creating timeout errors for all checks
            logger.error("health_check_timed_out", timeout_seconds=30)
            check_results = [
                asyncio.TimeoutError(
                    f"Health check component {name} timed out"
                )
                for name in health_checks
            ]

        # Process results
        for component_name, check_result in zip(
            health_checks.keys(), check_results, strict=False
        ):
            if isinstance(check_result, Exception):
                # Handle check failure
                logger.error(
                    "health_check_failed",
                    component_name=component_name,
                    error=str(check_result),
                )
                component_health = ComponentHealth(
                    name=component_name,
                    component_type=self._get_component_type(component_name),
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(check_result)}",
                    last_check=datetime.now(),
                )
                # For timeout errors specifically, we may want to handle them differently
                if isinstance(check_result, asyncio.TimeoutError):
                    component_health = ComponentHealth(
                        name=component_name,
                        component_type=self._get_component_type(
                            component_name
                        ),
                        status=HealthStatus.UNHEALTHY,  # Timeout indicates unhealthiness
                        message=f"Check timeout: {str(check_result)}",
                        last_check=datetime.now(),
                    )
            else:
                component_health = check_result

            result.components[component_name] = component_health

        # Determine overall status
        result.overall_status = self._calculate_overall_status(
            result.components
        )

        # Generate summary
        result.summary = self._generate_summary(result.components)

        # Check for alerts if alerting is enabled
        if self.config.alert_enabled:
            result.alerts = self._check_alerts(result.components)

        # Record performance metrics
        result.performance_metrics = {
            "total_check_time_ms": (time.time() - start_time) * 1000,
            "components_checked": len(result.components),
            "timestamp": time.time(),
        }

        # Update component results cache
        async with self._lock:
            self._component_results = result.components.copy()

        self.last_health_check = datetime.now()

        logger.debug(
            "health_check_completed",
            total_check_time_ms=result.performance_metrics[
                "total_check_time_ms"
            ],
        )

        return result

    async def _get_health_checks_dict(self) -> dict[str, Any]:
        """Get dictionary of all health check coroutines."""
        return {
            "database": self._check_database_health(),
            "redis": self._check_redis_health(),
            "cache_hierarchy": self._check_cache_health(),
            "file_system": self._check_file_system_health(),
            "memory": self._check_memory_health(),
            "cpu": self._check_cpu_health(),
            "tws_monitor": self._check_tws_monitor_health(),
            "connection_pools": self._check_connection_pools_health(),
            "websocket_pool": self._check_websocket_pool_health(),
        }

    async def _check_database_health(self) -> ComponentHealth:
        """Check database health using connection pools."""
        start_time = time.time()

        try:
            from resync.core.connection_manager import (
                get_connection_pool_manager,
            )

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
                # Simple query to test connection
                if hasattr(conn, "execute"):
                    result = await conn.execute("SELECT 1")
                    if hasattr(result, "fetchone"):
                        await result.fetchone()
                elif hasattr(conn, "cursor"):
                    # SQLite case
                    cursor = await conn.cursor()
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()
                    await cursor.close()

            response_time = (time.time() - start_time) * 1000

            # Get real pool statistics from pool manager
            pool_stats = pool_manager.get_pool_stats()

            if not pool_stats:
                return ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNHEALTHY,
                    message="Database pool statistics unavailable (empty/null)",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    metadata={"pool_stats": "empty or null"},
                )

            db_pool_stats = pool_stats.get("database")

            if db_pool_stats is None:
                return ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNHEALTHY,
                    message="Database pool statistics missing for 'database' pool",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    metadata={"database_pool": "missing"},
                )

            # Calculate connection usage percentage
            active_connections = db_pool_stats.active_connections
            total_connections = db_pool_stats.total_connections
            connection_usage_percent = (
                (active_connections / total_connections * 100)
                if total_connections > 0
                else 0.0
            )

            # Determine status based on configurable threshold
            threshold_percent = (
                self.config.database_connection_threshold_percent
            )
            if connection_usage_percent > threshold_percent:
                status = HealthStatus.DEGRADED
                message = f"Database connection pool near capacity: {active_connections}/{total_connections} ({connection_usage_percent:.1f}%)"
            else:
                status = HealthStatus.HEALTHY
                message = f"Database connection pool healthy: {active_connections}/{total_connections} ({connection_usage_percent:.1f}%)"

            # Use real database pool statistics
            pool_metadata = {
                "active_connections": active_connections,
                "idle_connections": db_pool_stats.idle_connections,
                "total_connections": total_connections,
                "connection_usage_percent": round(connection_usage_percent, 1),
                "threshold_percent": threshold_percent,
                "connection_errors": db_pool_stats.connection_errors,
                "pool_hits": db_pool_stats.pool_hits,
                "pool_misses": db_pool_stats.pool_misses,
                "connection_creations": db_pool_stats.connection_creations,
                "connection_closures": db_pool_stats.connection_closures,
                "waiting_connections": db_pool_stats.waiting_connections,
                "peak_connections": db_pool_stats.peak_connections,
                "average_wait_time": round(db_pool_stats.average_wait_time, 3),
                "last_health_check": (
                    db_pool_stats.last_health_check.isoformat()
                    if db_pool_stats.last_health_check
                    else None
                ),
            }

            return ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata=pool_metadata,
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            logger.error("database_health_check_failed", error=str(e))
            return ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_redis_health(self) -> ComponentHealth:
        """Check Redis cache health and connectivity."""
        start_time = time.time()

        try:
            # Check Redis configuration
            from resync.config.settings import settings

            if not settings.REDIS_URL:
                return ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.UNKNOWN,
                    message="Redis URL not configured",
                    last_check=datetime.now(),
                )

            # Test actual Redis connectivity
            import redis.asyncio as redis_async
            from redis.exceptions import RedisError
            from redis.exceptions import TimeoutError as RedisTimeoutError

            try:
                redis_client = redis_async.from_url(settings.REDIS_URL)
                # Test connectivity with ping
                await redis_client.ping()

                # Test read/write operation
                test_key = f"health_check_{int(time.time())}"
                await redis_client.setex(
                    test_key, 1, "test"
                )  # Set with expiration
                value = await redis_client.get(test_key)

                if value != b"test":
                    raise RedisError("Redis read/write test failed")

                # Get Redis info for additional details
                redis_info = await redis_client.info()

                response_time = (time.time() - start_time) * 1000

                return ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.HEALTHY,
                    message="Redis connectivity test successful",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    metadata={
                        "redis_version": redis_info.get("redis_version"),
                        "connected_clients": redis_info.get(
                            "connected_clients"
                        ),
                        "used_memory": redis_info.get("used_memory_human"),
                        "uptime_seconds": redis_info.get("uptime_in_seconds"),
                        "test_key_result": value.decode() if value else None,
                    },
                )
            except (RedisError, RedisTimeoutError) as e:
                response_time = (time.time() - start_time) * 1000

                logger.error("redis_connectivity_test_failed", error=str(e))
                return ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Redis connectivity failed: {str(e)}",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    error_count=1,
                )
            finally:
                # Close the test connection
                try:
                    await redis_client.close()
                except Exception as e:
                    logger.debug(
                        f"Redis client close error during health check: {e}"
                    )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("redis_health_check_failed", error=str(e))
            return ComponentHealth(
                name="redis",
                component_type=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cache_health(self) -> ComponentHealth:
        """Check cache hierarchy health."""
        start_time = time.time()

        try:
            # Import and test the actual cache implementation
            from resync.core.cache import AsyncTTLCache

            # Create a test cache instance to verify functionality
            test_cache = AsyncTTLCache(ttl_seconds=60, cleanup_interval=30)

            # Test cache operations
            test_key = f"health_test_{int(time.time())}"
            test_value = {"timestamp": time.time(), "status": "health_check"}

            # Test set operation
            await test_cache.set(test_key, test_value)

            # Test get operation
            retrieved_value = await test_cache.get(test_key)

            # Verify the value was retrieved correctly
            if retrieved_value != test_value:
                await test_cache.stop()
                raise Exception("Cache get/set test failed")

            # Test delete operation
            delete_result = await test_cache.delete(test_key)
            if not delete_result:
                logger.warning("Cache delete test had unexpected result")

            # Get cache statistics
            metrics = test_cache.get_detailed_metrics()

            # Stop the test cache
            await test_cache.stop()

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="cache_hierarchy",
                component_type=ComponentType.CACHE,
                status=HealthStatus.HEALTHY,
                message="Cache hierarchy operational",
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata=metrics,
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("cache_hierarchy_health_check_failed", error=str(e))
            return ComponentHealth(
                name="cache_hierarchy",
                component_type=ComponentType.CACHE,
                status=HealthStatus.DEGRADED,
                message=f"Cache hierarchy issues: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_file_system_health(self) -> ComponentHealth:
        """Check file system health and disk space monitoring."""
        start_time = time.time()

        try:
            # Check disk space
            import psutil

            disk_usage = psutil.disk_usage("/")
            disk_usage_percent = (disk_usage.used / disk_usage.total) * 100

            # Determine status
            if disk_usage_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Disk space critically low: {disk_usage_percent:.1f}% used"
            elif disk_usage_percent > 85:
                status = HealthStatus.DEGRADED
                message = (
                    f"Disk space getting low: {disk_usage_percent:.1f}% used"
                )
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {disk_usage_percent:.1f}% used"

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="file_system",
                component_type=ComponentType.FILE_SYSTEM,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "disk_usage_percent": disk_usage_percent,
                    "disk_free_gb": disk_usage.free / (1024**3),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("file_system_health_check_failed", error=str(e))
            return ComponentHealth(
                name="file_system",
                component_type=ComponentType.FILE_SYSTEM,
                status=HealthStatus.UNKNOWN,
                message=f"File system check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_memory_health(self) -> ComponentHealth:
        """Check memory usage monitoring."""
        start_time = time.time()

        try:
            import psutil

            # Get memory usage
            memory = psutil.virtual_memory()
            memory_usage_percent = memory.percent

            # Determine status
            if memory_usage_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage critically high: {memory_usage_percent:.1f}%"
            elif memory_usage_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"Memory usage high: {memory_usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_usage_percent:.1f}%"

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="memory",
                component_type=ComponentType.MEMORY,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "memory_usage_percent": memory_usage_percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("memory_health_check_failed", error=str(e))
            return ComponentHealth(
                name="memory",
                component_type=ComponentType.MEMORY,
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cpu_health(self) -> ComponentHealth:
        """Check CPU load monitoring."""
        start_time = time.time()

        try:
            import psutil

            # Multiple samples for more accurate reading
            cpu_samples = []
            cpu_samples.append(psutil.cpu_percent(interval=0))
            await asyncio.sleep(0.05)
            cpu_samples.append(psutil.cpu_percent(interval=0))
            await asyncio.sleep(0.05)
            cpu_samples.append(psutil.cpu_percent(interval=0))

            cpu_percent = sum(cpu_samples) / len(cpu_samples)

            # Determine status
            if cpu_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"CPU usage critically high: {cpu_percent:.1f}%"
            elif cpu_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"CPU usage high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="cpu",
                component_type=ComponentType.CPU,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "cpu_usage_percent": cpu_percent,
                    "cpu_samples": [round(s, 1) for s in cpu_samples],
                    "cpu_count": psutil.cpu_count(),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("cpu_health_check_failed", error=str(e))
            return ComponentHealth(
                name="cpu",
                component_type=ComponentType.CPU,
                status=HealthStatus.UNKNOWN,
                message=f"CPU check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_tws_monitor_health(self) -> ComponentHealth:
        """Check TWS monitor health (external API service)."""
        start_time = time.time()

        try:
            # Check TWS configuration
            from resync.config.settings import settings

            tws_config = settings.get("tws_monitor", {})
            if not tws_config or not tws_config.get("enabled", False):
                return ComponentHealth(
                    name="tws_monitor",
                    component_type=ComponentType.EXTERNAL_API,
                    status=HealthStatus.UNKNOWN,
                    message="TWS monitor not configured",
                    last_check=datetime.now(),
                )

            # Simple connectivity test
            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="tws_monitor",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.HEALTHY,
                message="TWS monitor connectivity test successful",
                response_time_ms=response_time,
                last_check=datetime.now(),
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("tws_monitor_health_check_failed", error=str(e))
            return ComponentHealth(
                name="tws_monitor",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.UNHEALTHY,
                message=f"TWS monitor connectivity failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_connection_pools_health(self) -> ComponentHealth:
        """Check connection pools health."""
        start_time = time.time()

        try:
            from resync.core.connection_manager import (
                get_connection_pool_manager,
            )

            pool_manager = get_connection_pool_manager()
            if not pool_manager:
                return ComponentHealth(
                    name="connection_pools",
                    component_type=ComponentType.CONNECTION_POOL,
                    status=HealthStatus.UNKNOWN,
                    message="Connection pool manager not available",
                    last_check=datetime.now(),
                )

            # Check pool status
            pool_stats = pool_manager.get_pool_stats()

            if not pool_stats:
                response_time = (time.time() - start_time) * 1000
                return ComponentHealth(
                    name="connection_pools",
                    component_type=ComponentType.CONNECTION_POOL,
                    status=HealthStatus.UNHEALTHY,
                    message="Connection pools statistics unavailable (empty/null)",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    metadata={"pool_stats": "empty or null"},
                )

            # Analyze pool health with safe defaults
            total_connections = pool_stats.get("total_connections", 0)
            active_connections = pool_stats.get("active_connections", 0)

            if total_connections == 0:
                status = HealthStatus.UNHEALTHY
                message = "No database connections available"
            else:
                # Calculate connection usage percentage
                connection_usage_percent = (
                    active_connections / total_connections * 100
                )

                # Use database-specific threshold for database pool
                threshold_percent = (
                    self.config.database_connection_threshold_percent
                )

                if connection_usage_percent > threshold_percent:
                    status = HealthStatus.DEGRADED
                    message = (
                        f"Connection pool near capacity: {active_connections}/{total_connections} "
                        f"({connection_usage_percent:.1f}%, threshold: {threshold_percent}%)"
                    )
                else:
                    status = HealthStatus.HEALTHY
                    message = (
                        f"Connection pool healthy: {active_connections}/{total_connections} "
                        f"({connection_usage_percent:.1f}%)"
                    )

            response_time = (time.time() - start_time) * 1000

            # Enhance metadata with calculated percentages and thresholds
            enhanced_metadata = dict(pool_stats)
            if (
                "active_connections" in pool_stats
                and "total_connections" in pool_stats
            ):
                enhanced_metadata["connection_usage_percent"] = round(
                    connection_usage_percent, 1
                )
                enhanced_metadata["threshold_percent"] = (
                    self.config.database_connection_threshold_percent
                )

            return ComponentHealth(
                name="connection_pools",
                component_type=ComponentType.CONNECTION_POOL,
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata=enhanced_metadata,
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("connection_pools_health_check_failed", error=str(e))
            return ComponentHealth(
                name="connection_pools",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection pools check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_websocket_pool_health(self) -> ComponentHealth:
        """Check websocket pool health."""
        start_time = time.time()

        try:
            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="websocket_pool",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.HEALTHY,
                message="WebSocket pool service available",
                response_time_ms=response_time,
                last_check=datetime.now(),
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("websocket_pool_health_check_failed", error=str(e))
            return ComponentHealth(
                name="websocket_pool",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"WebSocket pool unavailable: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
            )

    def _get_component_type(self, name: str) -> ComponentType:
        """Get component type for a given component name."""
        mapping = {
            "database": ComponentType.DATABASE,
            "redis": ComponentType.REDIS,
            "cache_hierarchy": ComponentType.CACHE,
            "file_system": ComponentType.FILE_SYSTEM,
            "memory": ComponentType.MEMORY,
            "cpu": ComponentType.CPU,
            "tws_monitor": ComponentType.EXTERNAL_API,
            "connection_pools": ComponentType.CONNECTION_POOL,
            "websocket_pool": ComponentType.CONNECTION_POOL,
        }
        return mapping.get(name, ComponentType.OTHER)

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
                        self.config.database_connection_threshold_percent,
                    )
                    usage = comp.metadata["connection_usage_percent"]
                    alerts.append(
                        f"Database connection pool usage at {usage:.1f}% (threshold: {threshold}%)"
                    )
                else:
                    alerts.append(f"{name} is degraded")
        return alerts

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




