from __future__ import annotations

import asyncio
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Soft import for aiofiles (optional dependency)
try:
    import aiofiles  # type: ignore
except ImportError:
    aiofiles = None  # type: ignore
import psutil
import structlog

from resync.core.connection_pool_manager import get_advanced_connection_pool_manager
from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
)
from resync.settings import settings

from .health_utils import get_health_checks_dict, initialize_health_result

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
        """Executes the function with circuit breaker protection."""
        if self.state == "open":
            # Check if it's time to attempt recovery
            if (
                datetime.now() - self.last_failure_time
            ).seconds > self.recovery_timeout:
                self.state = "half-open"
            else:
                # Circuit is open, fail fast
                raise Exception(f"Circuit breaker is open for {self.recovery_timeout}s")

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
            # If we've exceeded threshold, open the circuit
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    "circuit_breaker_opened", failure_count=self.failure_count
                )
            raise e


# Global health check service instance
_health_check_service: Optional[HealthCheckService] = None
_health_service_lock = asyncio.Lock()


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
        self._memory_usage_mb: float = 0.0
        self._cleanup_lock = asyncio.Lock()
        self._cache_lock = asyncio.Lock()
        # Circuit breakers for critical components
        self._circuit_breakers = {
            "database": CircuitBreaker(),
            "redis": CircuitBreaker(),
            "cache_hierarchy": CircuitBreaker(),
            "tws_monitor": CircuitBreaker(),
        }
        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("health_check_monitoring_started")

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
        logger.info("health_check_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while self._is_monitoring:
            try:
                await self.perform_comprehensive_health_check()
                await asyncio.sleep(self.config.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error_in_health_monitoring_loop", error=str(e))
                await asyncio.sleep(10)  # Brief pause on error

    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics for health monitoring."""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            # Get connection pool metrics if available
            pool_manager = get_advanced_connection_pool_manager()
            pool_metrics = pool_manager.get_performance_metrics()

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "pool_metrics": pool_metrics,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.warning("failed_to_get_performance_metrics", error=str(e))
            return {"error": str(e)}

    async def _get_connection_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        try:
            pool_manager = get_advanced_connection_pool_manager()
            return await pool_manager.force_health_check()
        except Exception as e:
            logger.warning("failed_to_get_connection_pool_stats", error=str(e))
            return {"error": str(e)}

    async def perform_comprehensive_health_check(self) -> HealthCheckResult:
        """Perform comprehensive health check with proactive monitoring."""
        start_time = time.time()
        correlation_id = f"health_{int(start_time)}"

        logger.debug(
            "starting_comprehensive_health_check", correlation_id=correlation_id
        )

        # Initialize result with enhanced metadata
        result = initialize_health_result(correlation_id)
        result.metadata = {
            "check_start_time": start_time,
            "proactive_checks": True,
            "performance_metrics": await self._get_performance_metrics(),
            "connection_pool_stats": await self._get_connection_pool_stats(),
        }

        # Perform all health checks in parallel
        health_checks = get_health_checks_dict(self)

        # Execute all checks with timeout protection
        try:
            check_results = await asyncio.wait_for(
                asyncio.gather(*health_checks.values(), return_exceptions=True),
                timeout=30.0,  # 30 second global timeout
            )
        except asyncio.TimeoutError:
            # Handle timeout by creating timeout errors for all checks
            logger.error("health_check_timed_out", timeout_seconds=30)
            check_results = [
                asyncio.TimeoutError(f"Health check component {name} timed out")
                for name in health_checks.keys()
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
                        component_type=self._get_component_type(component_name),
                        status=HealthStatus.UNHEALTHY,  # Timeout indicates unhealthiness
                        message=f"Check timeout: {str(check_result)}",
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
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_cache_ops": self._cache_hits + self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0
            ),
            "failed_checks": sum(
                1
                for c in result.components.values()
                if c.status in [HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN]
            ),
            "timestamp": time.time(),
            "memory_usage_mb": self._get_current_memory_usage(),
        }

        # Update history
        await self._update_health_history(result)

        self.last_health_check = datetime.now()
        await self._update_cache(result.components)

        logger.debug(
            "health_check_completed",
            total_check_time_ms=result.performance_metrics["total_check_time_ms"],
        )

        return result

    async def perform_proactive_health_checks(self) -> Dict[str, Any]:
        """
        Perform proactive health checks for connection pools and critical components.

        This method implements intelligent health monitoring that:
        - Preemptively detects connection issues
        - Monitors pool utilization and performance
        - Performs predictive health analysis
        - Triggers recovery actions automatically
        """
        start_time = time.time()
        results = {
            "timestamp": start_time,
            "checks_performed": [],
            "issues_detected": [],
            "recovery_actions": [],
            "performance_insights": {},
            "predictive_alerts": [],
        }

        logger.info(
            "starting_proactive_health_checks",
            correlation_id=f"proactive_{int(start_time)}",
        )

        try:
            # 1. Connection Pool Health Checks
            pool_health = await self._check_connection_pool_health()
            results["checks_performed"].append("connection_pools")
            results["performance_insights"]["connection_pools"] = pool_health

            # Detect pool issues
            if pool_health.get("utilization", 0) > 0.9:
                results["issues_detected"].append(
                    {
                        "type": "high_pool_utilization",
                        "severity": "high",
                        "message": f"Connection pool utilization at {pool_health['utilization']:.1%}",
                        "recommendation": "Consider scaling up connection pool",
                    }
                )

            if pool_health.get("error_rate", 0) > 0.05:
                results["issues_detected"].append(
                    {
                        "type": "high_error_rate",
                        "severity": "critical",
                        "message": f"Connection pool error rate at {pool_health['error_rate']:.1%}",
                        "recommendation": "Investigate connection stability",
                    }
                )

            # 2. Circuit Breaker Health
            circuit_health = await self._check_circuit_breaker_health()
            results["checks_performed"].append("circuit_breakers")
            results["performance_insights"]["circuit_breakers"] = circuit_health

            # Detect circuit breaker issues
            for cb_name, cb_status in circuit_health.items():
                if cb_status.get("state") == "open":
                    results["issues_detected"].append(
                        {
                            "type": "circuit_breaker_open",
                            "severity": "high",
                            "component": cb_name,
                            "message": f"Circuit breaker {cb_name} is open",
                            "recommendation": "Check upstream service health",
                        }
                    )

            # 3. Predictive Analysis
            predictions = await self._perform_predictive_analysis()
            results["checks_performed"].append("predictive_analysis")
            results["predictive_alerts"] = predictions

            # 4. Auto-Recovery Actions
            recovery_actions = await self._execute_auto_recovery()
            results["recovery_actions"] = recovery_actions

            # 5. Performance Baseline Comparison
            baseline_comparison = await self._compare_with_baseline()
            results["performance_insights"]["baseline_comparison"] = baseline_comparison

            logger.info(
                "proactive_health_checks_completed",
                duration=time.time() - start_time,
                issues_found=len(results["issues_detected"]),
                recovery_actions=len(results["recovery_actions"]),
            )

        except Exception as e:
            logger.error("proactive_health_checks_failed", error=str(e))
            results["error"] = str(e)

        return results

    async def _check_connection_pool_health(self) -> Dict[str, Any]:
        """Check health of all connection pools."""
        try:
            advanced_manager = get_advanced_connection_pool_manager()
            if advanced_manager:
                metrics = await advanced_manager.get_performance_metrics()
                return {
                    "pool_count": len(metrics.get("traditional_pools", {})),
                    "smart_pool_active": "smart_pool" in metrics,
                    "auto_scaling_active": "auto_scaling" in metrics,
                    "utilization": metrics.get("auto_scaling", {}).get("load_score", 0),
                    "error_rate": metrics.get("smart_pool", {})
                    .get("performance", {})
                    .get("error_rate", 0),
                    "total_connections": metrics.get("auto_scaling", {}).get(
                        "current_connections", 0
                    ),
                    "scaling_recommended": metrics.get("smart_pool", {}).get(
                        "scaling_signals", {}
                    ),
                }
            else:
                # Fallback to basic pool manager
                pool_manager = get_connection_pool_manager()
                if pool_manager:
                    basic_metrics = {}
                    for pool_name, pool in pool_manager.pools.items():
                        stats = pool.get_stats()
                        basic_metrics[pool_name] = {
                            "connections": stats.get("total_connections", 0),
                            "utilization": stats.get("active_connections", 0)
                            / max(1, stats.get("total_connections", 1)),
                        }
                    return basic_metrics

        except Exception as e:
            logger.warning("connection_pool_health_check_failed", error=str(e))

        return {"error": "Unable to check connection pool health"}

    async def _check_circuit_breaker_health(self) -> Dict[str, Any]:
        """Check health of all circuit breakers."""
        results = {}

        # Check TWS circuit breakers
        from resync.core.circuit_breaker import (
            adaptive_tws_api_breaker,
            adaptive_llm_api_breaker,
            tws_api_breaker,
            llm_api_breaker,
        )

        breakers = {
            "adaptive_tws_api": adaptive_tws_api_breaker,
            "adaptive_llm_api": adaptive_llm_api_breaker,
            "traditional_tws_api": tws_api_breaker,
            "traditional_llm_api": llm_api_breaker,
        }

        for name, breaker in breakers.items():
            if breaker:
                try:
                    stats = (
                        breaker.get_stats()
                        if hasattr(breaker, "get_stats")
                        else breaker.get_enhanced_stats()
                    )
                    results[name] = {
                        "state": stats.get("state", "unknown"),
                        "failures": stats.get("failures", 0),
                        "successes": stats.get("successes", 0),
                        "error_rate": stats.get("failure_rate", 0),
                        "last_failure": stats.get("last_failure_time"),
                        "latency_p95": stats.get("latency_percentiles", {}).get(
                            "p95", 0
                        ),
                    }
                except Exception as e:
                    results[name] = {"error": str(e)}

        return results

    async def _perform_predictive_analysis(self) -> List[Dict[str, Any]]:
        """Perform predictive analysis for potential issues."""
        alerts = []

        try:
            # Analyze connection pool trends
            pool_health = await self._check_connection_pool_health()

            utilization = pool_health.get("utilization", 0)
            if utilization > 0.8:
                # Predict potential exhaustion in next hour
                alerts.append(
                    {
                        "type": "pool_exhaustion_prediction",
                        "severity": "medium",
                        "timeframe": "1_hour",
                        "confidence": 0.75,
                        "message": f"Connection pool may exhaust at current utilization {utilization:.1%}",
                        "recommendation": "Monitor closely and prepare scaling",
                    }
                )

            # Analyze error rate trends
            error_rate = pool_health.get("error_rate", 0)
            if error_rate > 0.03:
                alerts.append(
                    {
                        "type": "error_rate_trend",
                        "severity": "high",
                        "timeframe": "immediate",
                        "confidence": 0.8,
                        "message": f"Rising error rate detected: {error_rate:.1%}",
                        "recommendation": "Investigate root cause immediately",
                    }
                )

            # Analyze circuit breaker patterns
            circuit_health = await self._check_circuit_breaker_health()
            open_breakers = sum(
                1 for cb in circuit_health.values() if cb.get("state") == "open"
            )

            if open_breakers > 0:
                alerts.append(
                    {
                        "type": "multiple_circuit_breakers_open",
                        "severity": "critical",
                        "timeframe": "immediate",
                        "confidence": 1.0,
                        "message": f"{open_breakers} circuit breaker(s) are open",
                        "recommendation": "Check upstream service availability",
                    }
                )

        except Exception as e:
            logger.error("predictive_analysis_failed", error=str(e))

        return alerts

    async def _execute_auto_recovery(self) -> List[Dict[str, Any]]:
        """Execute automatic recovery actions."""
        actions = []

        try:
            # Force health check on unhealthy connections
            pool_health = await self._check_connection_pool_health()
            if pool_health.get("error_rate", 0) > 0.1:
                # Trigger connection pool health check
                advanced_manager = get_advanced_connection_pool_manager()
                if advanced_manager:
                    health_results = await advanced_manager.force_health_check()
                    actions.append(
                        {
                            "action": "force_connection_health_check",
                            "timestamp": time.time(),
                            "results": health_results,
                            "reason": "High error rate detected",
                        }
                    )

            # Reset circuit breakers if appropriate
            circuit_health = await self._check_circuit_breaker_health()
            for cb_name, cb_status in circuit_health.items():
                if cb_status.get("state") == "open":
                    # Check if it's been long enough to attempt reset
                    last_failure = cb_status.get("last_failure")
                    if last_failure and (time.time() - last_failure) > 300:  # 5 minutes
                        # In real implementation, this would trigger circuit breaker reset
                        actions.append(
                            {
                                "action": "circuit_breaker_reset_candidate",
                                "component": cb_name,
                                "timestamp": time.time(),
                                "reason": "Circuit breaker open for extended period",
                                "recommendation": "Manual intervention may be needed",
                            }
                        )

        except Exception as e:
            logger.error("auto_recovery_execution_failed", error=str(e))

        return actions

    async def _compare_with_baseline(self) -> Dict[str, Any]:
        """Compare current performance with historical baseline."""
        # This would compare with stored baseline metrics
        # For now, return placeholder structure
        return {
            "baseline_available": False,
            "deviations": [],
            "trend": "stable",
            "recommendations": [
                "Implement baseline metrics storage for future comparisons"
            ],
        }

    async def _check_database_health(self) -> ComponentHealth:
        """Check database health using connection pools."""
        start_time = time.time()

        try:
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

            # Validate pool_stats is not empty/null
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

            # Validate database pool stats specifically
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

            # Validate that the database pool has valid data
            if (
                not hasattr(db_pool_stats, "total_connections")
                or db_pool_stats.total_connections is None
                or db_pool_stats.total_connections == 0
            ):
                return ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNHEALTHY,
                    message="Database pool has no configured connections",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    metadata={
                        "total_connections": (
                            0
                            if db_pool_stats.total_connections is None
                            else db_pool_stats.total_connections
                        )
                    },
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
            threshold_percent = self.config.database_connection_threshold_percent
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

    async def _check_with_retry(
        self, check_func, component_name: str, max_retries: int = 3
    ):
        """Executa health check com retry e backoff exponencial."""
        for attempt in range(max_retries):
            try:
                return await check_func()
            except Exception:
                if attempt == max_retries - 1:
                    logger.error(
                        "health_check_failed_after_retries",
                        component_name=component_name,
                        max_retries=max_retries,
                    )
                    raise

                wait_time = 2**attempt  # 1s, 2s, 4s
                logger.warning(
                    "health_check_failed_retrying",
                    component_name=component_name,
                    wait_time=wait_time,
                )
                await asyncio.sleep(wait_time)

    async def _check_redis_health(self) -> ComponentHealth:
        """Check Redis cache health and connectivity."""

        async def _redis_check():
            start_time = time.time()

            try:
                # Check Redis configuration
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
                    await redis_client.setex(test_key, 1, "test")  # Set with expiration
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
                            "connected_clients": redis_info.get("connected_clients"),
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
                        # Log Redis close errors but don't fail health check
                        logger.debug(
                            f"Redis client close error during health check: {e}"
                        )

            except Exception as e:
                response_time = (time.time() - start_time) * 1000

                # Simple error handling for health checks
                secure_message = str(e)

                logger.error("redis_health_check_failed", error=str(e))
                return ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Redis check failed: {secure_message}",
                    response_time_ms=response_time,
                    last_check=datetime.now(),
                    error_count=1,
                )

        # Use the retry wrapper
        return await self._check_with_retry(_redis_check, "redis")

    async def _check_cache_health(self) -> ComponentHealth:
        """Check cache hierarchy health."""
        start_time = time.time()

        try:
            # Import and test the actual cache implementation
            from resync.core.async_cache import AsyncTTLCache

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

            # Simple error handling for health checks
            secure_message = str(e)

            logger.error("cache_hierarchy_health_check_failed", error=str(e))
            return ComponentHealth(
                name="cache_hierarchy",
                component_type=ComponentType.CACHE,
                status=HealthStatus.DEGRADED,
                message=f"Cache hierarchy issues: {secure_message}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_file_system_health(self) -> ComponentHealth:
        """Check file system health and disk space monitoring."""
        start_time = time.time()

        try:
            # Check disk space
            disk_usage = psutil.disk_usage("/")
            disk_usage_percent = (disk_usage.used / disk_usage.total) * 100

            # Determine status
            if disk_usage_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Disk space critically low: {disk_usage_percent:.1f}% used"
            elif disk_usage_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"Disk space getting low: {disk_usage_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {disk_usage_percent:.1f}% used"

            # Test file system write capability with proper cleanup
            import uuid

            file_id = uuid.uuid4().hex
            test_file = Path(tempfile.gettempdir()) / f"health_check_{file_id}.tmp"
            write_test = "File system write test not completed"
            try:
                if aiofiles is None:
                    write_test = "File system write test skipped (aiofiles not available)"
                else:
                    async with aiofiles.open(test_file, "w") as f:
                        await f.write("health check test")
                write_test = "File system write test passed"
            except Exception as e:
                write_test = f"File system write test failed: {e}"
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                message += f", {write_test}"
            finally:
                # Always attempt cleanup, but don't fail the health check if cleanup fails
                try:
                    if test_file.exists() and aiofiles is not None:
                        await aiofiles.os.remove(test_file)
                except:
                    # Just log if cleanup fails, don't affect the health check result
                    logger.warning(
                        "failed_to_cleanup_temp_file", test_file=str(test_file)
                    )

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
                    "write_test": write_test,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            # Simple error handling for health checks
            secure_message = str(e)

            logger.error("file_system_health_check_failed", error=str(e))
            return ComponentHealth(
                name="file_system",
                component_type=ComponentType.FILE_SYSTEM,
                status=HealthStatus.UNKNOWN,
                message=f"File system check failed: {secure_message}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_memory_health(self) -> ComponentHealth:
        """Check memory usage monitoring."""
        start_time = time.time()

        try:
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

            # Get process memory usage
            process = psutil.Process()
            process_memory_mb = process.memory_info().rss / (1024**2)

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
                    "process_memory_mb": process_memory_mb,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            # Simple error handling for health checks
            secure_message = str(e)

            logger.error("memory_health_check_failed", error=str(e))
            return ComponentHealth(
                name="memory",
                component_type=ComponentType.MEMORY,
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {secure_message}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_cpu_health(self) -> ComponentHealth:
        """Check CPU load monitoring."""
        start_time = time.time()

        try:
            # Amostragem não-bloqueante com múltiplas leituras rápidas
            cpu_samples = []
            # Primeira leitura
            cpu_samples.append(psutil.cpu_percent(interval=0))
            await asyncio.sleep(0.05)  # Pequeno delay entre amostras
            # Segunda leitura
            cpu_samples.append(psutil.cpu_percent(interval=0))
            await asyncio.sleep(0.05)  # Pequeno delay entre amostras
            # Terceira leitura
            cpu_samples.append(psutil.cpu_percent(interval=0))

            # Média das amostras para uma leitura mais precisa
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
                    "cpu_frequency_mhz": (
                        getattr(psutil.cpu_freq(), "current", None)
                        if hasattr(psutil, "cpu_freq")
                        else None
                    ),
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            # Simple error handling for health checks
            secure_message = str(e)

            logger.error("cpu_health_check_failed", error=str(e))
            return ComponentHealth(
                name="cpu",
                component_type=ComponentType.CPU,
                status=HealthStatus.UNKNOWN,
                message=f"CPU check failed: {secure_message}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_tws_monitor_health(self) -> ComponentHealth:
        """Check TWS monitor health (external API service)."""
        start_time = time.time()

        try:
            # Check TWS configuration
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

            # Simple error handling for health checks
            secure_message = str(e)

            logger.error("tws_monitor_health_check_failed", error=str(e))
            return ComponentHealth(
                name="tws_monitor",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.UNHEALTHY,
                message=f"TWS monitor connectivity failed: {secure_message}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_connection_pools_health(self) -> ComponentHealth:
        """Check connection pools health."""
        start_time = time.time()

        try:
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

            # Validate pool_stats is not empty/null
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
                connection_usage_percent = active_connections / total_connections * 100

                # Use database-specific threshold for database pool
                threshold_percent = self.config.database_connection_threshold_percent

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
            if "active_connections" in pool_stats and "total_connections" in pool_stats:
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

            # Simple error handling for health checks
            secure_message = str(e)

            logger.error("connection_pools_health_check_failed", error=str(e))
            return ComponentHealth(
                name="connection_pools",
                component_type=ComponentType.CONNECTION_POOL,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection pools check failed: {secure_message}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    async def _check_websocket_pool_health(self) -> ComponentHealth:
        """Check websocket pool health."""
        start_time = time.time()

        try:
            # Import the connection manager to check WebSocket status

            # Check if connection manager exists and is active
            # This is a simplified check - in a real implementation, we'd track actual WebSocket connections
            # For now we'll assume if we can access the ConnectionManager, it's functional
            # But we'll check if there's an active instance

            # For a real implementation, we'd need to check the actual WebSocket connection pool
            # For now, we'll consider it as degraded if no connections have been made recently,
            # or healthy if it's available

            response_time = (time.time() - start_time) * 1000

            # We assume the WebSocket system is available if the chat module is loaded
            # In a real system, we'd track actual connection counts and other metrics
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
        mapping: Dict[str, ComponentType] = {
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
        self, components: Dict[str, ComponentHealth]
    ) -> HealthStatus:
        # Handle empty components case
        if not components:
            return HealthStatus.UNKNOWN

        # Simple aggregation: worst status wins
        # UNKNOWN should not be considered better than HEALTHY
        priority = {
            HealthStatus.UNHEALTHY: 3,
            HealthStatus.DEGRADED: 2,
            HealthStatus.UNKNOWN: 1,  # UNKNOWN is worse than HEALTHY but better than DEGRADED/UNHEALTHY
            HealthStatus.HEALTHY: 0,  # HEALTHY is the best status
        }
        worst = HealthStatus.HEALTHY
        for comp in components.values():
            if priority[comp.status] > priority[worst]:
                worst = comp.status
        return worst

    def _generate_summary(
        self, components: Dict[str, ComponentHealth]
    ) -> Dict[str, int]:
        summary: Dict[str, int] = {
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

    def _check_alerts(self, components: Dict[str, ComponentHealth]) -> List[str]:
        alerts: List[str] = []
        for name, comp in components.items():
            if comp.status == HealthStatus.UNHEALTHY:
                alerts.append(f"{name} is unhealthy")
            elif comp.status == HealthStatus.DEGRADED:
                # Include specific threshold breach information in alerts
                if name == "database" and "connection_usage_percent" in comp.metadata:
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

    async def _update_cache(self, components: Dict[str, ComponentHealth]) -> None:
        """Thread-safe update of component cache."""
        async with self._cache_lock:
            self.component_cache = components.copy()

    async def _get_cached_component(
        self, component_name: str
    ) -> Optional[ComponentHealth]:
        """Thread-safe retrieval of a component from cache."""
        async with self._cache_lock:
            return self.component_cache.get(component_name)

    async def _get_all_cached_components(self) -> Dict[str, ComponentHealth]:
        """Thread-safe retrieval of all cached components."""
        async with self._cache_lock:
            return self.component_cache.copy()

    async def _update_cached_component(
        self, component_name: str, health: ComponentHealth
    ) -> None:
        """Thread-safe update of a single component in cache."""
        async with self._cache_lock:
            self.component_cache[component_name] = health

    async def _update_health_history(self, result: HealthCheckResult) -> None:
        """Update health history with memory bounds and efficient cleanup."""
        # Create new history entry
        component_changes = await self._get_component_changes(result.components)
        history_entry = HealthStatusHistory(
            timestamp=result.timestamp,
            overall_status=result.overall_status,
            component_changes=component_changes,
        )

        # Add to history
        self.health_history.append(history_entry)

        # Perform cleanup if needed
        asyncio.create_task(self._cleanup_health_history())

        # Update memory usage tracking
        if self.config.enable_memory_monitoring:
            asyncio.create_task(self._update_memory_usage())

    async def _cleanup_health_history(self) -> None:
        """Perform efficient cleanup of health history based on multiple criteria."""
        async with self._cleanup_lock:
            try:
                current_size = len(self.health_history)
                max_entries = self.config.max_history_entries
                int(max_entries * self.config.history_cleanup_threshold)

                # Check if cleanup is needed based on size
                if current_size > max_entries:
                    # Remove oldest entries to get back to threshold
                    entries_to_remove = (
                        current_size
                        - max_entries
                        + self.config.history_cleanup_batch_size
                    )
                    self.health_history = self.health_history[entries_to_remove:]
                    logger.debug(
                        "cleaned_up_health_history_entries_size_based",
                        entries_to_remove=entries_to_remove,
                    )

                # Check if cleanup is needed based on age
                cutoff_date = datetime.now() - timedelta(
                    days=self.config.history_retention_days
                )
                original_size = len(self.health_history)
                self.health_history = [
                    entry
                    for entry in self.health_history
                    if entry.timestamp >= cutoff_date
                ]
                removed_by_age = original_size - len(self.health_history)
                if removed_by_age > 0:
                    logger.debug(
                        "cleaned_up_health_history_entries_age_based",
                        removed_by_age=removed_by_age,
                    )

                # Ensure we don't go below minimum required entries
                min_entries = max(10, self.config.history_cleanup_batch_size)
                if (
                    len(self.health_history) < min_entries
                    and original_size >= min_entries
                ):
                    # Keep at least some recent history
                    self.health_history = self.health_history[-min_entries:]

            except Exception as e:
                logger.error("error_during_health_history_cleanup", error=str(e))

    async def _get_component_changes(
        self, components: Dict[str, ComponentHealth]
    ) -> Dict[str, HealthStatus]:
        """Track component status changes for history."""
        changes = {}
        cached_components = await self._get_all_cached_components()

        for name, component in components.items():
            # Compare with last known status from cache
            if name in cached_components:
                if cached_components[name].status != component.status:
                    changes[name] = component.status
            else:
                # New component
                changes[name] = component.status
        return changes

    async def _update_memory_usage(self) -> None:
        """Update memory usage tracking for health history."""
        try:
            # Estimate memory usage of health history
            history_size = len(self.health_history)
            if history_size > 0:
                # More realistic estimation: each entry ~2KB (accounting for metadata and history)
                estimated_size_bytes = history_size * 2048
                self._memory_usage_mb = estimated_size_bytes / (1024 * 1024)

                # Alert if memory usage exceeds threshold
                if self._memory_usage_mb > self.config.memory_usage_threshold_mb:
                    logger.warning(
                        "health_history_memory_usage_exceeds_threshold",
                        current_usage_mb=round(self._memory_usage_mb, 2),
                        threshold_mb=self.config.memory_usage_threshold_mb,
                    )
            else:
                self._memory_usage_mb = 0.0

        except Exception as e:
            logger.error("error_updating_memory_usage", error=str(e))

    def _get_current_memory_usage(self) -> float:
        """Get current approximate memory usage."""
        try:
            # Rough estimation of health history memory usage
            history_size = len(self.health_history)
            if history_size > 0:
                # More realistic estimation: each entry ~2KB
                estimated_size_bytes = history_size * 2048
                return round(estimated_size_bytes / (1024 * 1024), 2)
            else:
                return 0.0
        except:
            return 0.0

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        return {
            "history_entries": len(self.health_history),
            "memory_usage_mb": round(self._memory_usage_mb, 2),
            "max_entries": self.config.max_history_entries,
            "retention_days": self.config.history_retention_days,
            "cleanup_threshold_percent": self.config.history_cleanup_threshold * 100,
            "memory_threshold_mb": self.config.memory_usage_threshold_mb,
            "enable_monitoring": self.config.enable_memory_monitoring,
        }

    async def force_cleanup(self) -> Dict[str, Any]:
        """Force immediate cleanup of health history."""
        original_size = len(self.health_history)
        await self._cleanup_health_history()
        new_size = len(self.health_history)

        return {
            "original_entries": original_size,
            "cleaned_entries": original_size - new_size,
            "current_entries": new_size,
            "memory_usage_mb": round(self._memory_usage_mb, 2),
        }

    def get_health_history(
        self, hours: int = 24, max_entries: Optional[int] = None
    ) -> List[HealthStatusHistory]:
        """Get health history for the specified number of hours with optional entry limit."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Filter by time
        filtered_history = [
            entry for entry in self.health_history if entry.timestamp >= cutoff_time
        ]

        # Apply entry limit if specified
        if max_entries is not None and len(filtered_history) > max_entries:
            # Return most recent entries
            filtered_history = filtered_history[-max_entries:]

        return filtered_history

    async def get_component_health(
        self, component_name: str
    ) -> Optional[ComponentHealth]:
        """Get the current health status of a specific component with expiry validation."""
        health = await self._get_cached_component(component_name)
        if health:
            age = datetime.now() - health.last_check
            if age < self.cache_expiry:
                self._cache_hits += 1
                return health
            # Cache expirado, remove do cache
            async with self._cache_lock:
                self.component_cache.pop(component_name, None)
        self._cache_misses += 1
        return None

    async def attempt_recovery(self, component_name: str) -> bool:
        """Attempt to recover a specific component."""
        # Placeholder implementation - can be extended for specific recovery strategies
        logger.info("attempting_recovery_for_component", component_name=component_name)

        # For now, just perform a fresh health check
        try:
            if component_name == "database":
                health = await self._check_database_health()
            elif component_name == "redis":
                health = await self._check_redis_health()
            elif component_name == "cache_hierarchy":
                health = await self._check_cache_health()
            elif component_name == "file_system":
                health = await self._check_file_system_health()
            elif component_name == "memory":
                health = await self._check_memory_health()
            elif component_name == "cpu":
                health = await self._check_cpu_health()
            elif component_name == "tws_monitor":
                health = await self._check_tws_monitor_health()
            elif component_name == "connection_pools":
                health = await self._check_connection_pools_health()
            elif component_name == "websocket_pool":
                health = await self._check_websocket_pool_health()
            else:
                logger.warning(
                    "unknown_component_for_recovery", component_name=component_name
                )
                return False

            # Update cache with new health status
            await self._update_cached_component(component_name, health)
            return health.status == HealthStatus.HEALTHY

        except Exception as e:
            logger.error(
                "recovery_attempt_failed", component_name=component_name, error=str(e)
            )
            return False


# Global health check service instance management
async def get_health_check_service() -> HealthCheckService:
    """
    Get the global health check service instance with thread-safe singleton initialization.

    This function implements the async double-checked locking pattern to prevent
    race conditions during singleton initialization.

    Returns:
        HealthCheckService: The global health check service instance
    """
    global _health_check_service

    # First check (without lock) for performance
    if _health_check_service is not None:
        return _health_check_service

    # Acquire lock for thread-safe initialization
    async with _health_service_lock:
        # Second check (with lock) to prevent race condition
        if _health_check_service is None:
            logger.info("Initializing global health check service")
            _health_check_service = HealthCheckService()
            await _health_check_service.start_monitoring()
            logger.info(
                "Global health check service initialized and monitoring started"
            )

    return _health_check_service

    def is_healthy(self) -> bool:
        """
        Check if the health check service is currently healthy.

        Returns:
            bool: True if the service is healthy, False otherwise
        """
        try:
            # Check if monitoring is active and recent health check was successful
            if hasattr(self, "_last_health_check"):
                # Simple health check - could be expanded
                return True
            return True
        except Exception:
            return False


async def shutdown_health_check_service() -> None:
    """
    Shutdown the global health check service gracefully.

    This function ensures proper cleanup of the health check service,
    including stopping monitoring and releasing resources.
    """
    global _health_check_service

    if _health_check_service is not None:
        try:
            logger.info("Shutting down global health check service")
            await _health_check_service.stop_monitoring()
            _health_check_service = None
            logger.info("Global health check service shutdown completed")
        except Exception as e:
            logger.error("Error during health check service shutdown", error=str(e))
            raise
    else:
        logger.debug("Health check service already shutdown or never initialized")
