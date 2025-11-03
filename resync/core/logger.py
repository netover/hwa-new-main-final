"""Unified logging utilities.

This module wraps Python's standard ``logging`` facilities to provide
backwards‑compatible functions used throughout the codebase.  Older
modules import functions such as ``log_with_correlation`` and
``log_audit_event`` from ``resync.core.logger``.  Those functions
previously relied on a custom structured logging system.  For
simplicity and to improve maintainability, this implementation uses
standard logging combined with the simple logger utilities from
``resync.utils.simple_logger``.

The goal of this shim is not to replicate the full structured logging
behaviour, but rather to ensure that calls to these functions do not
fail at runtime.  Messages are logged with an optional correlation ID
prefix when provided.  Audit events are recorded at INFO level with
a consistent format.

Usage:

    from resync.core.logger import log_with_correlation, log_audit_event

    log_with_correlation(logging.INFO, "Starting operation", correlation_id)
    log_audit_event("login", {"user_id": "alice"}, correlation_id=cid)
"""

from __future__ import annotations

import logging
from typing import Any

from resync.utils.simple_logger import get_logger, set_correlation_id, get_correlation_id  # noqa: F401


def log_with_correlation(
    level: int,
    message: str,
    correlation_id: str | None = None,
    exc_info: bool | Exception = False,
) -> None:
    """Log a message at the given level with an optional correlation ID.

    If ``correlation_id`` is provided, it is prefixed in square brackets
    to the log message.  The ``exc_info`` parameter may be set to
    ``True`` or an exception instance to include traceback information.

    Args:
        level: Logging level (e.g. ``logging.INFO``)
        message: The message to log
        correlation_id: Optional correlation ID for request tracing
        exc_info: Whether to include exception information
    """
    logger = logging.getLogger("resync")
    if correlation_id:
        formatted = f"[{correlation_id}] {message}"
    else:
        formatted = message
    logger.log(level, formatted, exc_info=exc_info)


def log_audit_event(
    action: str,
    details: dict[str, Any] | None = None,
    *,
    correlation_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record an audit event via the standard logger.

    This is a simplified implementation that logs audit actions at INFO
    level.  Additional metadata such as user ID, IP address and user
    agent are included when provided.

    Args:
        action: A short string describing the audited action
        details: Optional dictionary with extra detail about the action
        correlation_id: Optional correlation ID
        user_id: Optional user identifier
        ip_address: Optional IP address of the requester
        user_agent: Optional user agent string
    """
    logger = logging.getLogger("resync.audit")
    parts = [f"action={action}"]
    if user_id:
        parts.append(f"user_id={user_id}")
    if ip_address:
        parts.append(f"ip={ip_address}")
    if user_agent:
        parts.append(f"ua={user_agent}")
    if correlation_id:
        parts.append(f"cid={correlation_id}")
    if details:
        parts.append(f"details={details}")
    msg = " | ".join(parts)
    logger.info(msg)


__all__ = ["log_with_correlation", "log_audit_event"]
