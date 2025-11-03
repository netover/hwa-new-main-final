"""
Connection Pool Monitoring API Endpoints
REST API for monitoring optimized connection pools in 20-user environment
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from resync.utils.simple_logger import get_logger

from resync.core.pools.connection_pool_monitor import (
    get_connection_pool_monitor,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/pools", tags=["connection-pools"])


@router.get("/metrics", summary="Get connection pool metrics")
async def get_pool_metrics(
    pool_name: str = Query(None, description="Specific pool name (optional)")
) -> JSONResponse:
    """
    Get real-time metrics for connection pools.

    Returns comprehensive metrics including:
    - Active/idle/total connections
    - Utilization percentage
    - Wait times and error counts
    - Health status
    """
    try:
        monitor = await get_connection_pool_monitor()
        metrics = monitor.get_pool_metrics(pool_name)

        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "data": metrics,
            }
        )

    except Exception as e:
        logger.error("pool_metrics_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pool metrics: {str(e)}",
        )


@router.get("/alerts", summary="Get active connection pool alerts")
async def get_pool_alerts() -> JSONResponse:
    """
    Get all active connection pool alerts.

    Alerts include utilization warnings, wait time issues,
    error rate problems, and pool exhaustion events.
    """
    try:
        monitor = await get_connection_pool_monitor()
        alerts = monitor.get_active_alerts()

        # Group alerts by severity
        alerts_by_severity = {
            "critical": [a for a in alerts if a["severity"] == "critical"],
            "warning": [a for a in alerts if a["severity"] == "warning"],
            "info": [a for a in alerts if a["severity"] == "info"],
        }

        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "data": {
                    "total_alerts": len(alerts),
                    "alerts_by_severity": alerts_by_severity,
                    "all_alerts": alerts,
                },
            }
        )

    except Exception as e:
        logger.error("pool_alerts_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve pool alerts: {str(e)}"
        )


@router.get("/health", summary="Get connection pool health overview")
async def get_pool_health() -> JSONResponse:
    """
    Get overall connection pool health status.

    Provides a high-level view of pool health including:
    - Overall system health
    - Pool utilization summary
    - Active alerts count
    - Recommendations
    """
    try:
        monitor = await get_connection_pool_monitor()
        metrics = monitor.get_pool_metrics()
        alerts = monitor.get_active_alerts()
        status = monitor.get_monitoring_status()

        # Calculate health score
        health_score = _calculate_health_score(metrics, alerts)

        # Generate recommendations
        recommendations = _generate_health_recommendations(metrics, alerts)

        health_status = "healthy"
        if health_score < 70:
            health_status = "critical"
        elif health_score < 85:
            health_status = "warning"

        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "data": {
                    "health_status": health_status,
                    "health_score": health_score,
                    "pools_count": len(metrics),
                    "active_alerts": len(alerts),
                    "monitoring_active": status["monitoring_active"],
                    "recommendations": recommendations,
                    "pool_summary": _summarize_pool_metrics(metrics),
                },
            }
        )

    except Exception as e:
        logger.error("pool_health_check_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to check pool health: {str(e)}"
        )


@router.get("/status", summary="Get monitoring system status")
async def get_monitoring_status() -> JSONResponse:
    """
    Get the status of the connection pool monitoring system.

    Includes monitoring state, thresholds, and system information.
    """
    try:
        monitor = await get_connection_pool_monitor()
        status = monitor.get_monitoring_status()

        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "data": status,
            }
        )

    except Exception as e:
        logger.error("monitoring_status_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve monitoring status: {str(e)}",
        )


@router.post("/force-health-check", summary="Force immediate health check")
async def force_health_check() -> JSONResponse:
    """
    Force an immediate health check of all connection pools.

    This endpoint triggers health checks outside the normal schedule
    for immediate diagnostics.
    """
    try:
        monitor = await get_connection_pool_monitor()

        # Force metrics update
        await monitor._update_metrics()
        await monitor._perform_health_checks()
        await monitor._check_alerts()

        metrics = monitor.get_pool_metrics()
        alerts = monitor.get_active_alerts()

        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "message": "Health check completed",
                "data": {
                    "pools_checked": len(metrics),
                    "alerts_found": len(alerts),
                    "pool_health": {
                        name: m.get("health_status", "unknown")
                        for name, m in metrics.items()
                    },
                },
            }
        )

    except Exception as e:
        logger.error("forced_health_check_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to perform health check: {str(e)}"
        )


def _calculate_health_score(
    metrics: dict[str, Any], alerts: list[dict[str, Any]]
) -> float:
    """Calculate overall health score (0-100)."""
    if not metrics:
        return 0.0

    total_score = 0.0
    pool_count = len(metrics)

    for _pool_name, pool_metrics in metrics.items():
        pool_score = 100.0

        # Deduct points for high utilization
        utilization = pool_metrics.get("utilization_percent", 0)
        if utilization > 90:
            pool_score -= 30
        elif utilization > 80:
            pool_score -= 15

        # Deduct points for high wait times
        wait_time = pool_metrics.get("avg_wait_time_ms", 0)
        if wait_time > 500:
            pool_score -= 25
        elif wait_time > 100:
            pool_score -= 10

        # Deduct points for errors
        errors = pool_metrics.get("error_count", 0)
        if errors > 10:
            pool_score -= 20
        elif errors > 5:
            pool_score -= 10

        # Deduct points for unhealthy status
        if pool_metrics.get("health_status") != "healthy":
            pool_score -= 15

        total_score += max(0, pool_score)

    # Deduct points for active alerts
    critical_alerts = sum(
        1 for alert in alerts if alert["severity"] == "critical"
    )
    warning_alerts = sum(
        1 for alert in alerts if alert["severity"] == "warning"
    )

    total_score -= (critical_alerts * 10) + (warning_alerts * 5)

    return max(0.0, min(100.0, total_score / pool_count))


def _generate_health_recommendations(
    metrics: dict[str, Any], alerts: list[dict[str, Any]]
) -> list[str]:
    """Generate health recommendations based on current state."""
    recommendations = []

    # Check for high utilization
    for pool_name, pool_metrics in metrics.items():
        utilization = pool_metrics.get("utilization_percent", 0)
        if utilization > 90:
            recommendations.append(
                f"CRITICAL: {pool_name} pool utilization is {utilization:.1f}% - increase max connections immediately"
            )
        elif utilization > 80:
            recommendations.append(
                f"WARNING: {pool_name} pool utilization is {utilization:.1f}% - consider increasing max connections"
            )

    # Check for high wait times
    for pool_name, pool_metrics in metrics.items():
        wait_time = pool_metrics.get("avg_wait_time_ms", 0)
        if wait_time > 500:
            recommendations.append(
                f"CRITICAL: {pool_name} average wait time is {wait_time:.0f}ms - investigate connection bottlenecks"
            )
        elif wait_time > 100:
            recommendations.append(
                f"WARNING: {pool_name} average wait time is {wait_time:.0f}ms - monitor for performance issues"
            )

    # Check for unhealthy pools
    for pool_name, pool_metrics in metrics.items():
        if pool_metrics.get("health_status") != "healthy":
            recommendations.append(
                f"CRITICAL: {pool_name} pool health check failed - investigate connection issues"
            )

    # Check for critical alerts
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    if critical_alerts:
        recommendations.append(
            f"CRITICAL: {len(critical_alerts)} critical alerts active - immediate attention required"
        )

    if not recommendations:
        recommendations.append(
            "All connection pools are operating within normal parameters"
        )

    return recommendations


def _summarize_pool_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Create a summary of pool metrics."""
    if not metrics:
        return {}

    summary = {
        "total_pools": len(metrics),
        "healthy_pools": 0,
        "total_connections": 0,
        "active_connections": 0,
        "average_utilization": 0.0,
        "pools_by_status": {},
    }

    total_utilization = 0.0

    for _pool_name, pool_metrics in metrics.items():
        # Count healthy pools
        if pool_metrics.get("health_status") == "healthy":
            summary["healthy_pools"] += 1

        # Sum connections
        summary["total_connections"] += pool_metrics.get(
            "total_connections", 0
        )
        summary["active_connections"] += pool_metrics.get(
            "active_connections", 0
        )

        # Track utilization
        utilization = pool_metrics.get("utilization_percent", 0)
        total_utilization += utilization

        # Group by status
        status = pool_metrics.get("health_status", "unknown")
        summary["pools_by_status"][status] = (
            summary["pools_by_status"].get(status, 0) + 1
        )

    # Calculate averages
    if metrics:
        summary["average_utilization"] = total_utilization / len(metrics)

    return summary


# Export router for main application
pool_monitoring_router = router




