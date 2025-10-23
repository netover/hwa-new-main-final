"""Admin configuration API endpoints for Resync.

This module provides REST API endpoints for managing system configuration
through the /admin/config interface.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from resync.api.auth import verify_admin_credentials
from resync.core.fastapi_di import get_teams_integration, get_tws_client
from resync.core.interfaces import ITWSClient
from resync.core.teams_integration import TeamsIntegration
from resync.settings import settings

logger = logging.getLogger(__name__)

# API Router for admin endpoints
admin_router = APIRouter(prefix="/admin", tags=["Admin"])

# Templates will be obtained from app state at runtime

# Module-level singleton variables for dependency injection to avoid B008 errors
teams_integration_dependency = Depends(get_teams_integration)
tws_client_dependency = Depends(get_tws_client)


class TeamsConfigUpdate(BaseModel):
    """Teams configuration update model."""

    enabled: bool | None = Field(None, description="Enable Teams integration")
    webhook_url: str | None = Field(None, description="Teams webhook URL")
    channel_name: str | None = Field(None, description="Teams channel name")
    bot_name: str | None = Field(
        None, min_length=1, max_length=50, description="Bot display name"
    )
    avatar_url: str | None = Field(None, description="Bot avatar URL")
    enable_conversation_learning: bool | None = Field(
        None, description="Enable conversation learning"
    )
    enable_job_notifications: bool | None = Field(
        None, description="Enable job status notifications"
    )
    monitored_tws_instances: list[str] | None = Field(
        None, description="List of monitored TWS instances"
    )
    job_status_filters: list[str] | None = Field(
        None, description="Job status filters for notifications"
    )
    notification_types: list[str] | None = Field(
        None, description="Types of notifications to send"
    )


class AdminConfigResponse(BaseModel):
    """Admin configuration response model."""

    teams: Dict[str, Any] = Field(
        default_factory=dict, description="Teams integration configuration"
    )
    tws: Dict[str, Any] = Field(default_factory=dict, description="TWS configuration")
    system: Dict[str, Any] = Field(
        default_factory=dict, description="System configuration"
    )
    last_updated: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Last update timestamp",
    )


class TeamsHealthResponse(BaseModel):
    """Teams integration health check response."""

    status: Dict[str, Any] = Field(
        default_factory=dict, description="Teams integration status"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Health check timestamp",
    )


@admin_router.get("/", response_class=HTMLResponse, summary="Admin Dashboard")
async def admin_dashboard(request: Request) -> HTMLResponse:
    """Serve the admin configuration dashboard.

    Renders the HTML interface for managing system configuration.
    """
    try:
        # Create a new Jinja2Templates instance to avoid CSP/asyncio issues
        from pathlib import Path

        from fastapi.templating import Jinja2Templates

        templates_dir = Path(settings.BASE_DIR) / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        return templates.TemplateResponse("admin.html", {"request": request})
    except Exception as e:
        logger.error(f"Failed to render admin dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to render admin dashboard",
        ) from e


@admin_router.get(
    "/config",
    summary="Get Admin Configuration",
    response_model=AdminConfigResponse,
    dependencies=[Depends(verify_admin_credentials)],
)
async def get_admin_config(
    request: Request, teams_integration: TeamsIntegration = teams_integration_dependency
) -> AdminConfigResponse:
    """Get current admin configuration.

    Returns the current configuration for all system components
    that can be managed through the admin interface.
    """
    try:
        # Get Teams configuration
        teams_config = teams_integration.config

        teams_config_dict = {
            "enabled": teams_config.enabled,
            "webhook_url": teams_config.webhook_url,
            "channel_name": teams_config.channel_name,
            "bot_name": teams_config.bot_name,
            "avatar_url": teams_config.avatar_url,
            "enable_conversation_learning": teams_config.enable_conversation_learning,
            "enable_job_notifications": teams_config.enable_job_notifications,
            "monitored_tws_instances": teams_config.monitored_tws_instances,
            "job_status_filters": teams_config.job_status_filters,
            "notification_types": teams_config.notification_types,
        }

        # Get TWS configuration (simplified)
        tws_config = {
            "host": getattr(settings, "TWS_HOST", None),
            "port": getattr(settings, "TWS_PORT", None),
            "user": getattr(settings, "TWS_USER", None),
            "mock_mode": getattr(settings, "TWS_MOCK_MODE", False),
            "monitored_instances": getattr(settings, "MONITORED_TWS_INSTANCES", []),
        }

        # Get system configuration
        system_config = {
            "llm_endpoint": getattr(settings, "LLM_ENDPOINT", None),
            "admin_username": getattr(settings, "ADMIN_USERNAME", None),
            "debug": getattr(settings, "DEBUG", False),
            "environment": getattr(settings, "APP_ENV", "development"),
        }

        return AdminConfigResponse(
            teams=teams_config_dict,
            tws=tws_config,
            system=system_config,
            last_updated=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to get admin configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get configuration: {str(e)}",
        ) from e


@admin_router.put(
    "/config/teams",
    summary="Update Teams Configuration",
    response_model=AdminConfigResponse,
    dependencies=[Depends(verify_admin_credentials)],
)
async def update_teams_config(
    request: Request,
    config_update: TeamsConfigUpdate,
    teams_integration: TeamsIntegration = teams_integration_dependency,
) -> AdminConfigResponse:
    """Update Microsoft Teams integration configuration.

    Updates the Teams integration configuration with the provided values.
    Only provided fields will be updated.
    """
    try:
        # Get current Teams integration
        current_config = teams_integration.config

        # Update configuration with provided values
        update_fields = config_update.dict(exclude_unset=True)

        # Apply updates to configuration
        for field_name, field_value in update_fields.items():
            if hasattr(current_config, field_name) and field_value is not None:
                setattr(current_config, field_name, field_value)

        # Log configuration update
        logger.info(f"Teams configuration updated: {update_fields}")

        # Return updated configuration
        teams_config_dict = {
            "enabled": current_config.enabled,
            "webhook_url": current_config.webhook_url,
            "channel_name": current_config.channel_name,
            "bot_name": current_config.bot_name,
            "avatar_url": current_config.avatar_url,
            "enable_conversation_learning": current_config.enable_conversation_learning,
            "enable_job_notifications": current_config.enable_job_notifications,
            "monitored_tws_instances": current_config.monitored_tws_instances,
            "job_status_filters": current_config.job_status_filters,
            "notification_types": current_config.notification_types,
        }

        # Get other configuration sections
        tws_config = {
            "host": getattr(settings, "TWS_HOST", None),
            "port": getattr(settings, "TWS_PORT", None),
            "user": getattr(settings, "TWS_USER", None),
            "mock_mode": getattr(settings, "TWS_MOCK_MODE", False),
            "monitored_instances": getattr(settings, "MONITORED_TWS_INSTANCES", []),
        }

        system_config = {
            "llm_endpoint": getattr(settings, "LLM_ENDPOINT", None),
            "admin_username": getattr(settings, "ADMIN_USERNAME", None),
            "debug": getattr(settings, "DEBUG", False),
            "environment": getattr(settings, "APP_ENV", "development"),
        }

        return AdminConfigResponse(
            teams=teams_config_dict,
            tws=tws_config,
            system=system_config,
            last_updated=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to update Teams configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}",
        ) from e


@admin_router.get(
    "/config/teams/health",
    summary="Get Teams Integration Health",
    response_model=TeamsHealthResponse,
    dependencies=[Depends(verify_admin_credentials)],
)
async def get_teams_health(
    request: Request, teams_integration: TeamsIntegration = teams_integration_dependency
) -> TeamsHealthResponse:
    """Get Microsoft Teams integration health status.

    Returns the current health status of the Teams integration,
    including connectivity and configuration status.
    """
    try:
        health_status = await teams_integration.health_check()
        return TeamsHealthResponse(
            status=health_status, timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to get Teams health status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Teams health status: {str(e)}",
        ) from e


@admin_router.post(
    "/config/teams/test-notification",
    summary="Test Teams Notification",
    dependencies=[Depends(verify_admin_credentials)],
)
async def test_teams_notification(
    request: Request,
    message: str = "Test notification from Resync",
    teams_integration: TeamsIntegration = teams_integration_dependency,
) -> Dict[str, Any]:
    """Send test notification to Microsoft Teams.

    Sends a test notification to verify Teams integration is working correctly.
    """
    try:
        from resync.core.teams_integration import TeamsNotification

        # Create test notification
        notification = TeamsNotification(
            title="Resync Teams Integration Test",
            message=message,
            severity="info",
            additional_data={
                "test_timestamp": datetime.now().isoformat(),
                "instance": "admin_test",
            },
        )

        # Send notification
        success = await teams_integration.send_notification(notification)

        if success:
            return {
                "status": "success",
                "message": "Test notification sent successfully",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "message": "Failed to send test notification",
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to send test Teams notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}",
        ) from e


@admin_router.get(
    "/status",
    summary="Get Admin System Status",
    dependencies=[Depends(verify_admin_credentials)],
)
async def get_admin_status(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
    teams_integration: TeamsIntegration = teams_integration_dependency,
) -> Dict[str, Any]:
    """Get overall system status for administration.

    Returns comprehensive status information for system administration.
    """
    try:
        # Get TWS connection status
        try:
            tws_connected = await tws_client.check_connection()
            tws_status = "connected" if tws_connected else "disconnected"
        except Exception:
            tws_status = "error"

        # Get Teams integration status
        teams_health = await teams_integration.health_check()

        return {
            "system": {
                "status": "operational",
                "timestamp": datetime.now().isoformat(),
                "environment": getattr(settings, "APP_ENV", "development"),
                "debug": getattr(settings, "DEBUG", False),
            },
            "tws": {
                "status": tws_status,
                "host": getattr(settings, "TWS_HOST", "not_configured"),
            },
            "teams": teams_health,
            "version": getattr(settings, "PROJECT_VERSION", "unknown"),
        }

    except Exception as e:
        logger.error(f"Failed to get admin status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}",
        ) from e
