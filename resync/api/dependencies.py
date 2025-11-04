"""Shared FastAPI dependencies used across the Resync application."""

from __future__ import annotations

import re
import uuid
from typing import Any

import httpx
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:  # Redis is optional at runtime
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore

try:  # Neo4j is optional at runtime
    from neo4j import AsyncDriver  # type: ignore
except Exception:  # pragma: no cover
    AsyncDriver = None  # type: ignore

from resync.core.container import app_container
from resync.core.idempotency.manager import IdempotencyManager
from resync.utils.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
    ValidationError,
)
from resync.utils.simple_logger import get_logger

logger = get_logger(__name__)

# Global idempotency manager instance
_idempotency_manager: IdempotencyManager | None = None


# ============================================================================
# Shared client dependencies
# ============================================================================

def _missing_dependency(name: str) -> ServiceUnavailableError:
    return ServiceUnavailableError(f"{name} is not available.")


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTPX AsyncClient configured in the lifespan."""
    client = getattr(request.app.state, "http", None)
    if isinstance(client, httpx.AsyncClient):
        return client
    raise _missing_dependency("HTTP client")


async def get_redis_client(request: Request):
    """Return the shared Redis client when available."""
    if redis is None:
        raise _missing_dependency("Redis client")
    client = getattr(request.app.state, "redis", None)
    if client is None:
        raise _missing_dependency("Redis client")
    return client


def get_neo4j_driver(request: Request):
    """Return the shared Neo4j AsyncDriver when available."""
    driver = getattr(request.app.state, "neo4j", None)
    if driver is None or AsyncDriver is None:
        raise _missing_dependency("Neo4j driver")
    return driver


# ============================================================================
# Idempotency dependencies
# ============================================================================


async def get_idempotency_manager() -> IdempotencyManager:
    """Return the IdempotencyManager instance configured in the DI container."""
    if _idempotency_manager is not None:
        return _idempotency_manager
    try:
        manager = await app_container.get(IdempotencyManager)
        if manager is None:
            raise ServiceUnavailableError("Idempotency service is not available.")
        return manager
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("idempotency_manager_unavailable", error=str(exc), exc_info=True)
        raise ServiceUnavailableError("Idempotency service is not available.") from exc


async def get_idempotency_key(
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key")
) -> str | None:
    """Return the optional idempotency key header."""
    return x_idempotency_key


async def require_idempotency_key(
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key")
) -> str:
    """Validate a mandatory idempotency key header."""
    if not x_idempotency_key:
        raise ValidationError(
            message="Idempotency key is required for this operation",
            details={
                "header": "X-Idempotency-Key",
                "hint": "Include X-Idempotency-Key header with a unique UUID value.",
            },
        )

    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    if not uuid_pattern.match(x_idempotency_key):
        raise ValidationError(
            message="Invalid idempotency key format",
            details={
                "header": "X-Idempotency-Key",
                "expected": "UUID v4",
                "received": x_idempotency_key,
            },
        )

    return x_idempotency_key


async def initialize_idempotency_manager(redis_client: Any) -> None:
    """Initialise and cache the IdempotencyManager using a Redis backend."""
    global _idempotency_manager
    try:
        _idempotency_manager = IdempotencyManager(redis_client)
        logger.info("idempotency_manager_initialized", redis_available=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "idempotency_manager_initialization_failed",
            error=str(exc),
            redis_available=False,
        )


# ============================================================================
# Correlation ID dependencies
# ============================================================================


async def get_correlation_id(
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
    request: Request | None = None,
) -> str:
    """Return or generate a correlation ID for the current request context."""
    if x_correlation_id:
        return x_correlation_id

    from resync.core.context import get_correlation_id as ctx_get_correlation_id

    ctx_id = ctx_get_correlation_id()
    if ctx_id:
        return ctx_id
    return str(uuid.uuid4())


# ============================================================================
# Authentication dependencies (placeholders)
# ============================================================================

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """Return the authenticated user if credentials are provided."""
    if credentials:
        # Placeholder implementation until real authentication is wired.
        return {"token": credentials.credentials}
    return None


async def require_authentication(
    user: dict | None = Depends(get_current_user),
) -> dict:
    """Ensure that the request is authenticated."""
    if not user:
        raise AuthenticationError(
            message="Authentication required",
            details={"headers": {"WWW-Authenticate": "Bearer"}},
        )
    return user


# ============================================================================
# Rate limiting placeholder
# ============================================================================


async def check_rate_limit(request: Request) -> None:  # pragma: no cover - placeholder
    """Placeholder rate limiting dependency."""
    return None

