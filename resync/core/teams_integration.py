"""Microsoft Teams integration for Resync.

This module provides integration with Microsoft Teams for notifications,
job status monitoring, and conversational AI capabilities.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from resync.core.resilience import CircuitBreakerManager, CircuitBreakerError, retry_with_backoff
from resync.core.exceptions import NotificationError
from resync.settings import settings

from .shared_utils import TeamsNotification, create_job_status_notification

logger = structlog.get_logger(__name__)


@dataclass
class TeamsConfig:
    """Configuration for Microsoft Teams integration."""

    enabled: bool = False
    webhook_url: Optional[str] = None
    channel_name: Optional[str] = None
    bot_name: str = "Resync Bot"
    avatar_url: Optional[str] = None
    enable_conversation_learning: bool = False
    enable_job_notifications: bool = False
    monitored_tws_instances: List[str] = field(default_factory=list)
    job_status_filters: List[str] = field(
        default_factory=lambda: ["ABEND", "ERROR", "FAILED"]
    )
    notification_types: List[str] = field(
        default_factory=lambda: ["job_status", "alerts", "performance"]
    )


@dataclass
class TeamsNotification:
    """Structure for Teams notification data."""

    title: str
    message: str
    severity: str = "info"  # info, warning, error, critical
    timestamp: datetime = field(default_factory=datetime.now)
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    instance_name: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


class TeamsIntegration:
    """Microsoft Teams integration service."""

    def __init__(self, config: Optional[TeamsConfig] = None):
        """Initialize Teams integration service.

        Args:
            config: Teams configuration. If None, loads from settings.
        """
        self.config = config or self._load_config_from_settings()
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    def _load_config_from_settings(self) -> TeamsConfig:
        """Load Teams configuration from application settings."""
        config = TeamsConfig()

        # Load configuration from settings if available
        teams_settings = getattr(settings, "TEAMS_INTEGRATION", {})
        if teams_settings:
            config.enabled = teams_settings.get("enabled", False)
            config.webhook_url = teams_settings.get("webhook_url")
            config.channel_name = teams_settings.get("channel_name")
            config.bot_name = teams_settings.get("bot_name", "Resync Bot")
            config.avatar_url = teams_settings.get("avatar_url")
            config.enable_conversation_learning = teams_settings.get(
                "enable_conversation_learning", False
            )
            config.enable_job_notifications = teams_settings.get(
                "enable_job_notifications", False
            )
            config.monitored_tws_instances = teams_settings.get(
                "monitored_tws_instances", []
            )
            config.job_status_filters = teams_settings.get(
                "job_status_filters", ["ABEND", "ERROR", "FAILED"]
            )
            config.notification_types = teams_settings.get(
                "notification_types", ["job_status", "alerts", "performance"]
            )

        return config

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp client session."""
        async with self._session_lock:
            if self.session is None or self.session.closed:
                connector = aiohttp.TCPConnector(
                    limit=100, limit_per_host=30, ttl_dns_cache=300
                )
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={"Content-Type": "application/json"},
                )
            return self.session

    async def _close_session(self) -> None:
        """Close aiohttp client session."""
        async with self._session_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def send_notification(self, notification: TeamsNotification) -> bool:
        """Send notification to Microsoft Teams.

        Args:
            notification: Teams notification data

        Returns:
            True if notification was sent successfully, False otherwise

        Raises:
            NotificationError: If notification fails due to configuration issues
        """
        if not self.config.enabled:
            logger.debug("teams_notification_skipped", reason="integration_disabled")
            return False

        if not self.config.webhook_url:
            logger.warning(
                "teams_notification_failed", reason="webhook_url_not_configured"
            )
            raise NotificationError("Teams webhook URL not configured")

        try:
            # Format message for Teams
            teams_message = self._format_teams_message(notification)

            # Send to Teams webhook
            session = await self._get_session()
            async with session.post(
                self.config.webhook_url, json=teams_message
            ) as response:
                if response.status in [200, 201, 202, 204]:
                    logger.info("teams_notification_sent", title=notification.title)
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        "teams_notification_failed",
                        status=response.status,
                        error=error_text,
                    )
                    return False

        except aiohttp.ClientError as e:
            logger.error(
                "teams_notification_network_error", error=str(e), exc_info=True
            )
            raise NotificationError(
                f"Network error sending Teams notification: {e}"
            ) from e
        except Exception as e:
            logger.error(
                "teams_notification_unexpected_error", error=str(e), exc_info=True
            )
            raise NotificationError(
                f"Unexpected error sending Teams notification: {e}"
            ) from e

    def _format_teams_message(self, notification: TeamsNotification) -> Dict[str, Any]:
        """Format notification as Microsoft Teams message card.

        Args:
            notification: Teams notification data

        Returns:
            Formatted message card for Teams
        """
        # Determine color based on severity

        # Create adaptive card for Teams
        message_card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [
                            {
                                "type": "TextBlock",
                                "size": "Large",
                                "weight": "Bolder",
                                "text": notification.title,
                                "wrap": True,
                            },
                            {
                                "type": "TextBlock",
                                "text": notification.message,
                                "wrap": True,
                            },
                        ],
                        "actions": [],
                    },
                }
            ],
        }

        # Add additional information if available
        facts = []

        if notification.instance_name:
            facts.append({"title": "Instance", "value": notification.instance_name})

        if notification.job_id:
            facts.append({"title": "Job ID", "value": notification.job_id})

        if notification.job_status:
            facts.append({"title": "Job Status", "value": notification.job_status})

        # Add timestamp
        facts.append(
            {"title": "Timestamp", "value": notification.timestamp.isoformat()}
        )

        # Add facts to card if any exist
        if facts:
            message_card["attachments"][0]["content"]["body"].extend(
                [{"type": "FactSet", "facts": facts}]
            )

        # Add additional data if provided
        if notification.additional_data:
            additional_section = {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "**Additional Information:**",
                        "weight": "Bolder",
                    }
                ],
            }

            for key, value in notification.additional_data.items():
                additional_section["items"].append(
                    {"type": "TextBlock", "text": f"{key}: {value}", "wrap": True}
                )

            message_card["attachments"][0]["content"]["body"].append(additional_section)

        # Add custom styling
        if self.config.bot_name:
            message_card["attachments"][0]["content"][
                "$schema"
            ] = "http://adaptivecards.io/schemas/adaptive-card.json"

        return message_card

    async def monitor_job_status(
        self, job_data: Dict[str, Any], instance_name: str
    ) -> None:
        """Monitor job status and send notifications for configured job status changes.

        Args:
            job_data: Job status data from TWS
            instance_name: Name of the TWS instance
        """
        if not self.config.enabled or not self.config.enable_job_notifications:
            return

        # Check if this instance is being monitored
        if (
            self.config.monitored_tws_instances
            and instance_name not in self.config.monitored_tws_instances
        ):
            return

        # Check if job status matches filters
        job_status = job_data.get("status", "").upper()
        if job_status in [status.upper() for status in self.config.job_status_filters]:
            # Send notification
            notification = create_job_status_notification(
                job_data, instance_name, self.config.job_status_filters
            )

            if notification is None:
                return

            try:
                await self.send_notification(notification)
            except NotificationError as e:
                logger.error("job_status_notification_failed", error=str(e))
            except Exception as e:
                logger.error("job_status_notification_unexpected_error", error=str(e))

    async def learn_from_conversation(
        self, message: str, context: Dict[str, Any]
    ) -> None:
        """Learn from Teams conversation for AI enhancement.

        Args:
            message: Message content from Teams
            context: Message context (sender, timestamp, etc.)
        """
        if not self.config.enabled or not self.config.enable_conversation_learning:
            return

        logger.info("learning_from_teams_conversation", message_preview=message[:100])
        # This would integrate with the knowledge graph/learning system
        # For now, just log that we're learning from the conversation

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of Teams integration.

        Returns:
            Health status dictionary
        """
        status = {
            "enabled": self.config.enabled,
            "configured": bool(self.config.webhook_url),
            "conversation_learning": self.config.enable_conversation_learning,
            "job_notifications": self.config.enable_job_notifications,
            "monitored_instances": len(self.config.monitored_tws_instances),
            "last_check": datetime.now().isoformat(),
        }

        if self.config.enabled and self.config.webhook_url:
            try:
                # Test webhook connectivity
                session = await self._get_session()
                async with session.get(
                    self.config.webhook_url, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status["webhook_accessible"] = response.status in [
                        200,
                        405,
                    ]  # 405 is expected for GET on webhook
            except Exception as e:
                status["webhook_accessible"] = False
                status["webhook_error"] = str(e)
                logger.warning("teams_webhook_health_check_failed", error=str(e))

        return status

    async def shutdown(self) -> None:
        """Shutdown Teams integration service."""
        await self._close_session()
        logger.info("teams_integration_service_shutdown")


# Global Teams integration instance
_teams_integration: Optional[TeamsIntegration] = None


async def get_teams_integration() -> TeamsIntegration:
    """Get global Teams integration instance.

    Returns:
        TeamsIntegration instance
    """
    global _teams_integration
    if _teams_integration is None:
        _teams_integration = TeamsIntegration()
    return _teams_integration


async def shutdown_teams_integration() -> None:
    """Shutdown global Teams integration instance."""
    global _teams_integration
    if _teams_integration is not None:
        await _teams_integration.shutdown()
        _teams_integration = None
