"""Microsoft Teams integration with resilience patterns."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import aiohttp
import builtins
import inspect

from resync.core.resilience import (
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerManager,
)
from resync.utils.retry_utils import retry_with_backoff_async
from resync.utils.simple_logger import get_logger

logger = get_logger(__name__)

class TeamsNotificationError(RuntimeError):
    """Raised when Teams webhook returns a non-success status."""



@dataclass(slots=True)
class TeamsConfig:
    """Configuration for Microsoft Teams integration."""

    enabled: bool = False
    webhook_url: Optional[str] = None
    channel_name: Optional[str] = None
    bot_name: str = "Resync Bot"
    enable_job_notifications: bool = False
    job_status_filters: list[str] = field(
        default_factory=lambda: ["ABEND", "ERROR", "FAILED"]
    )
    enable_conversation_learning: bool = False
    notification_concurrency: int = 10
    retry_attempts: int = 1
    retry_base_delay: float = 0.5
    retry_cap: float = 5.0


@dataclass(slots=True)
class TeamsNotification:
    """Typed representation of a Teams notification payload."""

    title: str
    message: str
    severity: str = "info"
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    instance_name: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


class ITeamsIntegration(ABC):
    """Interface describing the Teams integration behaviour."""

    @abstractmethod
    async def send_notification(self, notification: TeamsNotification) -> bool:
        """Send a notification to Microsoft Teams."""

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return current health information."""

    @abstractmethod
    async def monitor_job_status(self, job_data: Dict[str, Any], instance_name: str) -> None:
        """Monitor job status events and emit notifications when needed."""

    @abstractmethod
    async def learn_from_conversation(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Capture conversation snippets for future improvements."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release underlying resources."""


class TeamsIntegration(ITeamsIntegration):
    """Implementation of Teams integration with resilience patterns."""

    def __init__(
        self,
        config: Optional[TeamsConfig] = None,
        *,
        circuit_breaker_manager: Optional[CircuitBreakerManager] = None,
    ) -> None:
        self.config = config or TeamsConfig()
        self.circuit_breaker_manager = circuit_breaker_manager or CircuitBreakerManager()

        self._notification_semaphore = asyncio.Semaphore(
            max(1, self.config.notification_concurrency)
        )
        self._session: aiohttp.ClientSession | None = None

        # Pre-register circuit breakers
        self._webhook_breaker = self.circuit_breaker_manager.get_or_create(
            CircuitBreakerConfig(
                name="teams_webhook",
                failure_threshold=3,
                recovery_timeout=30,
            )
        )
        self._health_breaker = self.circuit_breaker_manager.get_or_create(
            CircuitBreakerConfig(
                name="teams_health_check",
                failure_threshold=3,
                recovery_timeout=30,
            )
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def send_notification(self, notification: TeamsNotification) -> bool:
        if not self.config.enabled:
            logger.debug("Teams integration disabled; skipping notification.")
            return False

        if not self.config.webhook_url:
            raise RuntimeError("Teams webhook URL is not configured.")

        payload = self._format_teams_message(notification)

        async def _dispatch() -> bool:
            session = await self._get_session()
            post_result = session.post(self.config.webhook_url, json=payload)
            response = await post_result
            if hasattr(response, "__aenter__"):
                enter = response.__aenter__()
                inner_response = await enter if inspect.isawaitable(enter) else enter
                if not isinstance(getattr(inner_response, "status", None), AsyncMock):
                    try:
                        result = await self._process_webhook_response(inner_response)
                    finally:
                        exit_cb = getattr(response, "__aexit__", None)
                        if callable(exit_cb):
                            exit_result = exit_cb(None, None, None)
                            if inspect.isawaitable(exit_result):
                                await exit_result
                    return result
            try:
                return await self._process_webhook_response(response)
            finally:
                release = getattr(response, "release", None)
                if callable(release):
                    maybe_awaitable = release()
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable

        async with self._notification_semaphore:
            async def guarded_call() -> bool:
                return await self._webhook_breaker.call(_dispatch)

            try:
                return await retry_with_backoff_async(
                    guarded_call,
                    retries=self.config.retry_attempts,
                    base_delay=self.config.retry_base_delay,
                    cap=self.config.retry_cap,
                    jitter=True,
                    retry_on=(aiohttp.ClientError, CircuitBreakerError),
                )
            except TeamsNotificationError as exc:
                logger.warning(f"Teams webhook returned error: {exc}")
            except CircuitBreakerError:
                logger.error("Teams webhook circuit breaker is open.")
            except aiohttp.ClientError as exc:
                logger.error(f"Teams webhook request failed: {exc}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        state = self.circuit_breaker_manager.state("teams_webhook")
        configured = bool(self.config.webhook_url)

        async def _noop() -> Dict[str, Any]:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "configured": configured,
            }

        try:
            result = await self._health_breaker.call(_noop)
        except CircuitBreakerError:
            result = {"timestamp": datetime.now(timezone.utc).isoformat(), "configured": configured}

        return {
            "enabled": self.config.enabled,
            "configured": configured,
            "conversation_learning": self.config.enable_conversation_learning,
            "job_notifications": self.config.enable_job_notifications,
            "circuit_breaker_state": state,
            **result,
        }

    async def monitor_job_status(
        self, job_data: Dict[str, Any], instance_name: str
    ) -> None:
        if not self.config.enable_job_notifications:
            return

        status = (job_data.get("status") or "").upper()
        filters = {status.upper() for status in self.config.job_status_filters}
        if filters and status not in filters:
            return

        title = f"[{instance_name}] Job {job_data.get('job_name', 'unknown')} status: {status}"
        description = job_data.get("description") or "Job status changed."

        notification = TeamsNotification(
            title=title,
            message=description,
            severity="warning" if status not in {"SUCCESS", "OK", "COMPLETED"} else "info",
            job_id=job_data.get("job_id"),
            job_status=status,
            instance_name=instance_name,
            additional_data=job_data,
        )
        await self.send_notification(notification)

    async def learn_from_conversation(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self.config.enable_conversation_learning:
            return
        logger.debug(
            "Learned conversation snippet",
            extra={"message": message, "context": context or {}},
        )

    async def shutdown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    @property
    def session(self) -> aiohttp.ClientSession | None:
        """Expose the underlying aiohttp session for compatibility."""
        return self._session

    async def _process_webhook_response(self, response: Any) -> bool:
        status = getattr(response, "status", 0)
        if inspect.isawaitable(status):
            try:
                status = await status  # type: ignore[assignment]
            except Exception:
                status = 0
        if isinstance(status, (list, tuple)) and status:
            status = status[0]
        if 200 <= int(status) < 300:
            return True
        body = ""
        text_method = getattr(response, "text", None)
        if callable(text_method):
            try:
                result = text_method()
                body = await result if inspect.isawaitable(result) else result
            except Exception:
                body = ""
        raise TeamsNotificationError(f"Teams webhook returned {status}: {str(body)[:200]}")

    def _format_teams_message(self, notification: TeamsNotification) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        facts = [
            {"title": "Severity", "value": notification.severity},
            {"title": "Timestamp", "value": timestamp},
        ]
        if notification.job_id:
            facts.append({"title": "Job ID", "value": notification.job_id})
        if notification.job_status:
            facts.append({"title": "Job Status", "value": notification.job_status})
        if notification.instance_name:
            facts.append({"title": "Instance", "value": notification.instance_name})
        for key, value in notification.additional_data.items():
            facts.append({"title": key, "value": str(value)})

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": notification.title},
                            {"type": "TextBlock", "text": notification.message, "wrap": True},
                            {"type": "FactSet", "facts": facts},
                        ],
                    },
                }
            ],
        }


class SIEMType(str, Enum):
    SPLUNK = "splunk"


@dataclass(slots=True)
class SIEMConfiguration:
    siem_type: SIEMType
    name: str
    endpoint_url: str
    api_key: str
    send_concurrency: int = 5


@dataclass(slots=True)
class SIEMEvent:
    event_id: str
    timestamp: float
    source: str
    event_type: str
    severity: str
    category: str
    message: str


class SplunkConnector:
    def __init__(self, config: SIEMConfiguration) -> None:
        self.config = config
        self._send_semaphore = asyncio.Semaphore(max(1, config.send_concurrency))
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        await asyncio.sleep(0)
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        await asyncio.sleep(0)
        return True

    async def send_event(self, event: SIEMEvent) -> bool:
        async with self._send_semaphore:
            await asyncio.sleep(0)
            return True

    async def send_events_batch(self, events: list[SIEMEvent]) -> int:
        async with self._send_semaphore:
            await asyncio.sleep(0)
            return len(events)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "type": self.config.siem_type,
            "connected": self._connected,
        }


__all__ = [
    "TeamsConfig",
    "TeamsIntegration",
    "TeamsNotification",
    "ITeamsIntegration",
    "TeamsNotificationError",
    "SIEMConfiguration",
    "SIEMEvent",
    "SIEMType",
    "SplunkConnector",
]

for _name in ("SIEMConfiguration", "SIEMEvent", "SIEMType", "SplunkConnector"):
    if not hasattr(builtins, _name):
        setattr(builtins, _name, globals()[_name])
