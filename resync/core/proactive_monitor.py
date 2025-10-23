"""
Proactive Monitoring System

This module provides intelligent health monitoring that preemptively detects connection issues,
monitors pool utilization and performance, performs predictive health analysis, and triggers
recovery actions automatically.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import structlog

from resync.core.connection_pool_manager import (
    get_advanced_connection_pool_manager,
    get_connection_pool_manager,
)
from resync.core.health_service import HealthCheckService

logger = structlog.get_logger(__name__)


class ProactiveMonitor:
    """Proactive monitoring system for health checks."""

    def __init__(self, health_service: HealthCheckService):
        self.health_service = health_service

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
