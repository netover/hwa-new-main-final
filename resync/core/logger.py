"""Unified logging utilities with audit support."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from resync.utils.simple_logger import get_logger  # re-exported for compatibility

try:  # Optional import when audit subsystem is available
    from resync.core.audit_log import get_audit_log_manager
except Exception:  # pragma: no cover - defensive
    get_audit_log_manager = None  # type: ignore

SENSITIVE_KEYS = {
    "password",
    "api_key",
    "token",
    "secret",
    "credit_card",
    "cc",
    "access_key",
}


def _sanitize_audit_details(details: Mapping[str, Any] | Any) -> Any:
    """Recursively redact sensitive payload fields."""
    if isinstance(details, Mapping):
        sanitized: dict[str, Any] = {}
        for key, value in details.items():
            if key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "REDACTED"
            else:
                sanitized[key] = _sanitize_audit_details(value)
        return sanitized
    if isinstance(details, list):
        return [_sanitize_audit_details(item) for item in details]
    return details


def log_with_correlation(
    level: int,
    message: str,
    correlation_id: str | None = None,
    exc_info: bool | Exception = False,
) -> None:
    logger = logging.getLogger("resync")
    formatted = f"[{correlation_id}] {message}" if correlation_id else message
    logger.log(level, formatted, exc_info=exc_info)


def log_audit_event(
    action: str,
    details: dict[str, Any] | None = None,
    *,
    correlation_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    severity: str = "INFO",
    source_component: str | None = None,
) -> None:
    sanitized_details = _sanitize_audit_details(details or {})
    parts = [f"action={action}"]
    if user_id:
        parts.append(f"user_id={user_id}")
    if ip_address:
        parts.append(f"ip={ip_address}")
    if user_agent:
        parts.append(f"ua={user_agent}")
    if correlation_id:
        parts.append(f"cid={correlation_id}")
    parts.append(f"details={sanitized_details}")
    logger = logging.getLogger("resync.audit")
    logger.info(" | ".join(parts))

    if get_audit_log_manager:
        try:
            manager = get_audit_log_manager()
            manager.log_audit_event(
                action=action,
                user_id=user_id,
                details=sanitized_details,
                correlation_id=correlation_id,
                severity=severity,
                source_component=source_component,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to persist audit event")


__all__ = ["log_with_correlation", "log_audit_event", "_sanitize_audit_details", "get_logger"]
