"""
Simplified Health API

This module provides simplified health check endpoints that maintain API compatibility
while using the simplified health service implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from resync_new.models.health_models import (
    ComponentType,
    HealthStatus,
    get_status_color,
    get_status_description,
)

from resync.core.health.health_service_manager_simplified import (
    get_simplified_health_service,
    shutdown_simplified_health_service,
)

logger = logging.getLogger(__name__)

# Main health router
router = APIRouter(prefix="/health", tags=["health"])


# Health check response models (reusing existing models for compatibility)
class HealthSummaryResponse(BaseModel):
    """Health check summary response."""

    status: str
    status_color: str
    status_description: str
    timestamp: str
    correlation_id: str
    summary: dict[str, Any]
    alerts: list[str]
    performance_metrics: dict[str, Any]


class ComponentHealthResponse(BaseModel):
    """Individual component health response."""

    name: str
    component_type: str
    status: str
    status_color: str
    message: str
    response_time_ms: float | None = None
    last_check: str
    error_count: int
    metadata: dict[str, Any] | None = None


class DetailedHealthResponse(BaseModel):
    """Detailed health check response."""

    overall_status: str
    overall_status_color: str
    timestamp: str
    correlation_id: str
    components: dict[str, ComponentHealthResponse]
    summary: dict[str, Any]
    alerts: list[str]
    performance_metrics: dict[str, Any]
    history: list[dict[str, Any]]


class CoreHealthResponse(BaseModel):
    """Core components health response."""

    status: str
    status_color: str
    timestamp: str
    core_components: dict[str, ComponentHealthResponse]
    summary: dict[str, Any]


# Core components that are critical for system operation
CORE_COMPONENTS = {"database", "redis", "cache_hierarchy", "system_resources"}


@router.get("/", response_model=HealthSummaryResponse)
async def get_health_summary(
    auto_enable: bool = Query(
        default=False,
        description="Auto-enable system components if validation is successful",
    )
) -> HealthSummaryResponse:
    """
    Get overall system health summary with status indicators.

    Args:
        auto_enable: Whether to auto-enable system components if validation is successful

    Returns:
        HealthSummaryResponse: Overall system health status with color-coded indicators
    """
    try:
        health_service = await get_simplified_health_service()
        if not health_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simplified health service not initialized",
            )

        # Get system health status
        await health_service.get_system_health()

        # Get all component health results
        results = await health_service.run_all_checks()

        # Calculate overall status from results
        overall_status = HealthStatus.HEALTHY
        for result in results:
            for component in result.components.values():
                if component.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                    break
                if component.status == HealthStatus.DEGRADED:
                    overall_status = HealthStatus.DEGRADED

        # Create summary
        summary = {
            "total_components": len(results),
            "healthy": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.HEALTHY
            ),
            "degraded": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.DEGRADED
            ),
            "unhealthy": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.UNHEALTHY
            ),
            "unknown": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.UNKNOWN
            ),
            "auto_enable": auto_enable,
            "auto_enable_applied": auto_enable
            and overall_status != HealthStatus.UNHEALTHY,
        }

        return HealthSummaryResponse(
            status=overall_status.value,
            status_color=get_status_color(overall_status),
            status_description=get_status_description(overall_status),
            timestamp=datetime.now().isoformat(),
            correlation_id=f"health_summary_{int(datetime.now().timestamp())}",
            summary=summary,
            alerts=[],
            performance_metrics={},
        )
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check system error: {str(e)}",
        ) from e


@router.get("/core", response_model=CoreHealthResponse)
async def get_core_health() -> CoreHealthResponse:
    """
    Get health status for core system components only.

    Returns:
        CoreHealthResponse: Health status of core components with status indicators
    """
    try:
        health_service = await get_simplified_health_service()
        if not health_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simplified health service not initialized",
            )

        # Get all component health results
        results = await health_service.run_all_checks()

        # Filter only core components
        core_components = {}
        for result in results:
            for name, component in result.components.items():
                if name in CORE_COMPONENTS:
                    core_components[name] = ComponentHealthResponse(
                        name=component.name,
                        component_type=component.component_type.value,
                        status=component.status.value,
                        status_color=get_status_color(component.status),
                        message=component.message or "",
                        response_time_ms=component.response_time_ms,
                        last_check=component.last_check.isoformat(),
                        error_count=component.error_count,
                        metadata=component.metadata,
                    )

        # Calculate core status (more strict - any unhealthy core component = unhealthy overall)
        core_status = HealthStatus.HEALTHY
        for component in core_components.values():
            if component.status == HealthStatus.UNHEALTHY:
                core_status = HealthStatus.UNHEALTHY
                break
            if component.status == HealthStatus.DEGRADED:
                core_status = HealthStatus.DEGRADED

        # Generate core summary
        core_summary = {
            "total_core_components": len(core_components),
            "healthy_core_components": sum(
                1
                for c in core_components.values()
                if c.status == HealthStatus.HEALTHY
            ),
            "unhealthy_core_components": sum(
                1
                for c in core_components.values()
                if c.status == HealthStatus.UNHEALTHY
            ),
            "timestamp": datetime.now().isoformat(),
        }

        return CoreHealthResponse(
            status=core_status.value,
            status_color=get_status_color(core_status),
            timestamp=datetime.now().isoformat(),
            core_components=core_components,
            summary=core_summary,
        )
    except Exception as e:
        logger.error("Core health check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Core health check system error: {str(e)}",
        ) from e


@router.get("/detailed", response_model=DetailedHealthResponse)
async def get_detailed_health(
    include_history: bool = Query(
        False, description="Include health history in response"
    ),
    history_hours: int = Query(
        24, description="Hours of history to include", ge=1, le=168
    ),
) -> DetailedHealthResponse:
    """
    Get detailed health check with all components and optional history.

    Args:
        include_history: Whether to include historical health data
        history_hours: Number of hours of history to include (1-168)

    Returns:
        DetailedHealthResponse: Comprehensive health status with all components
    """
    try:
        health_service = await get_simplified_health_service()
        if not health_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simplified health service not initialized",
            )

        # Get all component health results
        results = await health_service.run_all_checks()

        # Convert components to response format
        components_response = {}
        for result in results:
            for name, component in result.components.items():
                components_response[name] = ComponentHealthResponse(
                    name=component.name,
                    component_type=component.component_type.value,
                    status=component.status.value,
                    status_color=get_status_color(component.status),
                    message=component.message or "",
                    response_time_ms=component.response_time_ms,
                    last_check=component.last_check.isoformat(),
                    error_count=component.error_count,
                    metadata=component.metadata,
                )

        # Calculate overall status
        overall_status = HealthStatus.HEALTHY
        for result in results:
            for component in result.components.values():
                if component.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                    break
                if component.status == HealthStatus.DEGRADED:
                    overall_status = HealthStatus.DEGRADED

        # Get history if requested (simplified service doesn't track history)
        history_data = []
        if include_history:
            # For simplified service, return empty history with a note
            history_data = [
                {
                    "timestamp": datetime.now().isoformat(),
                    "overall_status": overall_status.value,
                    "overall_status_color": get_status_color(overall_status),
                    "summary": "Simplified health service does not track history",
                }
            ]

        # Generate summary
        summary = {
            "total_components": len(results),
            "healthy": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.HEALTHY
            ),
            "degraded": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.DEGRADED
            ),
            "unhealthy": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.UNHEALTHY
            ),
            "unknown": sum(
                1
                for result in results
                for component in result.components.values()
                if component.status == HealthStatus.UNKNOWN
            ),
        }

        return DetailedHealthResponse(
            overall_status=overall_status.value,
            overall_status_color=get_status_color(overall_status),
            timestamp=datetime.now().isoformat(),
            correlation_id=f"health_detailed_{int(datetime.now().timestamp())}",
            components=components_response,
            summary=summary,
            alerts=[],
            performance_metrics={},
            history=history_data,
        )
    except Exception as e:
        logger.error("Detailed health check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Detailed health check system error: {str(e)}",
        ) from e


@router.get("/ready")
async def readiness_probe() -> dict[str, Any]:
    """
    Kubernetes readiness probe endpoint.

    Returns 503 Service Unavailable if core components are unhealthy,
    200 OK if system is ready to serve requests.

    Returns:
        dict[str, Any]: Readiness status with core component details
    """
    try:
        health_service = await get_simplified_health_service()
        if not health_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simplified health service not initialized",
            )

        # Get system health status
        system_status = await health_service.get_system_health()

        # Get all component health results
        results = await health_service.run_all_checks()

        # Filter only core components
        core_components = {}
        for result in results:
            for name, component in result.components.items():
                if name in CORE_COMPONENTS:
                    core_components[name] = {
                        "status": component.status.value,
                        "status_color": get_status_color(component.status),
                        "message": component.message,
                    }

        # System is ready if all core components are healthy
        ready = system_status != "critical" and all(
            component.status == HealthStatus.HEALTHY
            for result in results
            for name, component in result.components.items()
            if name in CORE_COMPONENTS
        )

        response_data = {
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.now().isoformat(),
            "core_components": core_components,
        }

        if not ready:
            # Return 503 Service Unavailable if not ready
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response_data,
            )

        return response_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness probe failed: %s", e)
        # Always return 503 on probe failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            },
        ) from e


@router.get("/live")
async def liveness_probe() -> dict[str, Any]:
    """
    Kubernetes liveness probe endpoint.

    Returns 503 Service Unavailable if the health check system itself is failing,
    200 OK if the system is alive and responding.

    Returns:
        dict[str, Any]: Liveness status
    """
    try:
        health_service = await get_simplified_health_service()
        if not health_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simplified health service not initialized",
            )

        # Simple liveness check - just verify the service is responding
        current_time = datetime.now()

        # System is considered alive if we can get the service
        return {
            "status": "alive",
            "timestamp": current_time.isoformat(),
            "message": "Simplified health service is responding",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Liveness probe failed: %s", e)
        # Always return 503 on probe failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "dead",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            },
        ) from e


@router.get("/metrics")
async def get_prometheus_metrics():
    """
    Get Prometheus metrics for health checks.

    Returns:
        Prometheus metrics in text format
    """
    try:
        health_service = await get_simplified_health_service()
        if not health_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simplified health service not initialized",
            )

        # Get metrics from health service
        metrics_content, content_type = health_service.get_prometheus_metrics()

        from fastapi import Response

        return Response(
            content=metrics_content,
            media_type=content_type,
        )
    except Exception as e:
        logger.error("Failed to get Prometheus metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}",
        ) from e


@router.get("/components")
async def list_components() -> dict[str, list[dict[str, str]]]:
    """
    List all available health check components.

    Returns:
        dict[str, list[dict[str, str]]]: List of available components
    """
    components = [
        {
            "name": "database",
            "type": ComponentType.DATABASE.value,
            "description": "Database connectivity and performance",
        },
        {
            "name": "redis",
            "type": ComponentType.REDIS.value,
            "description": "Redis cache connectivity",
        },
        {
            "name": "cache_hierarchy",
            "type": ComponentType.CACHE.value,
            "description": "Cache hierarchy health",
        },
        {
            "name": "system_resources",
            "type": ComponentType.OTHER.value,
            "description": "System resources (CPU, memory, disk)",
        },
        {
            "name": "websocket_pool",
            "type": ComponentType.WEBSOCKET.value,
            "description": "WebSocket connection pools",
        },
    ]

    return {"components": components}


@router.on_event("shutdown")
async def shutdown_health_service():
    """Shutdown simplified health service on application shutdown."""
    try:
        await shutdown_simplified_health_service()
        logger.info("Simplified health service shutdown completed")
    except Exception as e:
        logger.error("Error during simplified health service shutdown: %s", e)
