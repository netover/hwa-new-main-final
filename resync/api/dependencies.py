"""Dependências compartilhadas para endpoints FastAPI.

Este módulo fornece funções de dependência para injeção em endpoints,
incluindo gerenciamento de idempotência, autenticação, e obtenção de IDs de contexto.
"""


from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from resync.core.container import app_container
from resync.core.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
    ValidationError,
)
from resync.core.idempotency.manager import IdempotencyManager
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Global idempotency manager instance
_idempotency_manager: IdempotencyManager | None = None

# ============================================================================
# IDEMPOTENCY DEPENDENCIES
# ============================================================================


async def get_idempotency_manager() -> IdempotencyManager:
    """Obtém a instância do IdempotencyManager a partir do container de DI.

    Returns:
        IdempotencyManager configurado

    Raises:
        ServiceUnavailableError: Se o serviço de idempotência não estiver disponível.
    """
    # Try to use the initialized global manager first
    if _idempotency_manager is not None:
        return _idempotency_manager

    # Fallback to DI container
    try:
        return await app_container.get(IdempotencyManager)
    except Exception as e:
        logger.error("idempotency_manager_unavailable", error=str(e), exc_info=True)
        raise ServiceUnavailableError("Idempotency service is not available.")


async def get_idempotency_key(
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key")
) -> str | None:
    """Extrai idempotency key do header.

    Args:
        x_idempotency_key: Header X-Idempotency-Key

    Returns:
        Idempotency key ou None
    """
    return x_idempotency_key


async def require_idempotency_key(
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key")
) -> str:
    """Extrai e valida idempotency key obrigatória.

    Args:
        x_idempotency_key: Header X-Idempotency-Key

    Returns:
        Idempotency key

    Raises:
        ValidationError: Se key não foi fornecida
    """
    if not x_idempotency_key:
        raise ValidationError(
            message="Idempotency key is required for this operation",
            details={
                "header": "X-Idempotency-Key",
                "hint": "Include X-Idempotency-Key header with a unique UUID",
            },
        )

    # Validar formato (deve ser UUID v4)
    import re

    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    if not uuid_pattern.match(x_idempotency_key):
        raise ValidationError(
            message="Invalid idempotency key format",
            details={
                "header": "X-Idempotency-Key",
                "expected": "UUID v4 format",
                "received": x_idempotency_key,
            },
        )

    return x_idempotency_key


async def initialize_idempotency_manager(redis_client):
    """
    Initialize the global idempotency manager with Redis client.

    Args:
        redis_client: Redis async client for persistence
    """
    global _idempotency_manager
    try:
        # Initialize the global manager with the new refactored structure
        manager = IdempotencyManager(redis_client)
        # Store globally for dependency injection
        _idempotency_manager = manager

        logger.info("idempotency_manager_initialized", redis_available=True)

    except Exception as e:
        logger.error(
            "idempotency_manager_initialization_failed",
            error=str(e),
            redis_available=False,
        )
        # Create in-memory fallback
        # Note: In production, this should not be used
        # For now, we'll just log the error and continue


# ============================================================================
# CORRELATION ID DEPENDENCIES
# ============================================================================


async def get_correlation_id(
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
    request: Request | None = None,
) -> str:
    """Obtém ou gera correlation ID.

    Args:
        x_correlation_id: Header X-Correlation-ID
        request: Request object

    Returns:
        Correlation ID
    """
    if x_correlation_id:
        return x_correlation_id

    # Tentar obter do contexto
    from resync.core.context import get_correlation_id as get_ctx_correlation_id

    ctx_id = get_ctx_correlation_id()
    if ctx_id:
        return ctx_id

    # Gerar novo
    import uuid

    return str(uuid.uuid4())


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """Obtém usuário atual (placeholder).

    Args:
        credentials: Credenciais de autenticação injetadas pelo FastAPI.

    Returns:
        Um dicionário representando o usuário ou None se não autenticado.
    """
    # TODO: Implementar autenticação real
    if credentials:
        # Validar token e retornar usuário
        pass

    return None


async def require_authentication(
    user: dict | None = Depends(get_current_user),
) -> dict:
    """Garante que um usuário esteja autenticado.

    Args:
        user: O usuário obtido da dependência `get_current_user`.

    Returns:
        Dados do usuário

    Raises:
        AuthenticationError: Se o usuário não estiver autenticado.
    """
    if not user:
        raise AuthenticationError(
            message="Authentication required",
            details={"headers": {"WWW-Authenticate": "Bearer"}},
        )

    return user


# ============================================================================
# RATE LIMITING DEPENDENCIES
# ============================================================================


async def check_rate_limit(request: Request) -> None:
    """Verifica rate limit (placeholder).

    Args:
        request: Request object

    Raises:
        RateLimitError: Se o limite de taxa for excedido.
    """
    # TODO: Implementar verificação de rate limit
