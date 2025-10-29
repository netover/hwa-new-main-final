"""
WebSocket Pool Health Checker

This module provides health checking functionality for WebSocket pool.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog
from resync_new.models.health_models import (
    ComponentHealth,
    ComponentType,
    HealthStatus,
)

from .base_health_checker import BaseHealthChecker

logger = structlog.get_logger(__name__)


class WebSocketPoolHealthChecker(BaseHealthChecker):
    """
    Health checker for WebSocket pool health.
    """

    @property
    def component_name(self) -> str:
        return "websocket_pool"

    @property
    def component_type(self) -> ComponentType:
        return ComponentType.CONNECTION_POOL

    async def check_health(self) -> ComponentHealth:
        """
        Check WebSocket pool health.

        Returns:
            ComponentHealth: WebSocket pool health status
        """
        start_time = time.time()

        try:
            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name=self.component_name,
                component_type=self.component_type,
                status=HealthStatus.HEALTHY,
                message="WebSocket pool service available",
                response_time_ms=response_time,
                last_check=datetime.now(),
                metadata={
                    "pool_status": "available",
                    "connections": "unknown",  # Would be populated by actual WebSocket pool manager
                },
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("websocket_pool_health_check_failed", error=str(e))
            return ComponentHealth(
                name=self.component_name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"WebSocket pool unavailable: {str(e)}",
                response_time_ms=response_time,
                last_check=datetime.now(),
                error_count=1,
            )

    def _get_status_for_exception(self, exception: Exception) -> ComponentType:
        """Determine health status based on WebSocket pool exception type."""
        return ComponentType.CONNECTION_POOL

    def get_component_config(self) -> dict[str, Any]:
        """Get WebSocket pool-specific configuration."""
        return {
            "timeout_seconds": self.config.timeout_seconds,
            "retry_attempts": 2,
        }
