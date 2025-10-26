"""Application lifespan management.

This module handles FastAPI application startup and shutdown events,
managing the lifecycle of critical application components including:

- Database connections and pools
- Redis connections and health monitoring
- Background task schedulers
- Health check services
- Resource cleanup and graceful shutdown
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from redis.exceptions import (
    AuthenticationError as RedisAuthError,
    BusyLoadingError as RedisBusyLoadingError,
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from resync.api_gateway.container import setup_dependencies
from resync.core.container import app_container
from resync.core.exceptions import (
    ConfigurationError,
    RedisAuthError,
    RedisConnectionError,
    RedisInitializationError,
    RedisTimeoutError,
)
from resync.core.interfaces import IAgentManager, IKnowledgeGraph, ITWSClient
from resync.core.redis_init import RedisInitializer
from resync.core.structured_logger import get_logger
from resync.core.tws_monitor import get_tws_monitor, shutdown_tws_monitor
from resync.cqrs.dispatcher import initialize_dispatcher
from resync.settings import settings

logger = get_logger(__name__)
# Lazy initialization with environment flag
_EAGER = os.getenv("RESYNC_EAGER_BOOT") == "1"
_BOOTED = False

def boot_if_needed():
    """Boot lifespan components if needed, preventing multiple initializations."""
    global _BOOTED
    if _BOOTED:
        return
    # (mover para cá as inicializações que antes rodavam no import)
    # ex: registrar middlewares, carregar extensões, iniciar health checks leves…
    _BOOTED = True
    logger.info("Lifespan booted lazily.")

if _EAGER:
    boot_if_needed()

# Create a global RedisInitializer instance - lazy initialization
_redis_initializer = None

def get_redis_initializer() -> RedisInitializer:
    """Get the global Redis initializer instance with lazy initialization."""
    global _redis_initializer
    if _redis_initializer is None:
        _redis_initializer = RedisInitializer()
    return _redis_initializer

# Create a global RedisInitializer instance



@asynccontextmanager
async def redis_connection_manager() -> AsyncIterator:
    """
    Context manager para Redis com cleanup automático.

    Yields:
        Redis client validado

    Raises:
        RedisConnectionError: Falha de conexão
        RedisAuthError: Falha de autenticação
    """
    from resync.core.async_cache import get_redis_client

    client = None
    try:
        client = await get_redis_client()

        # Validar conexão antes de usar
        await client.ping()
        logger.info("redis_connection_validated")

        yield client

    except RedisConnectionError as e:
        logger.error(
            "redis_connection_failed",
            error=str(e),
            redis_url=settings.REDIS_URL.split("@")[-1],  # Sem senha no log
        )
        raise RedisConnectionError(
            "Não foi possível conectar ao Redis",
            details={
                "redis_url": settings.REDIS_URL.split("@")[-1],
                "error": str(e),
                "hint": "Verifique se Redis está rodando: redis-cli ping",
            },
        ) from e

    except RedisAuthError as e:
        logger.error("redis_auth_failed", error=str(e))
        raise RedisAuthError(
            "Falha de autenticação no Redis",
            details={"error": str(e), "hint": "Verifique REDIS_URL no .env"},
        ) from e

    except RedisTimeoutError as e:
        logger.error("redis_timeout", error=str(e))
        raise RedisTimeoutError(
            "Timeout ao conectar ao Redis",
            details={
                "error": str(e),
                "hint": "Redis pode estar sobrecarregado ou rede lenta",
            },
        ) from e

    finally:
        if client:
            try:
                await client.close()
                await client.connection_pool.disconnect()
                logger.debug("redis_connection_closed")
            except Exception as e:
                logger.warning(
                    "redis_cleanup_warning", error=type(e).__name__, message=str(e)
                )


async def initialize_redis_with_retry(
    max_retries: int = 3, base_backoff: float = 0.5, max_backoff: float = 5.0
) -> None:
    """
    Inicializa Redis com retry exponencial.

    Args:
        max_retries: Máximo de tentativas
        base_backoff: Tempo base de espera (segundos)
        max_backoff: Tempo máximo de espera (segundos)

    Raises:
        RedisConnectionError: Redis inacessível após retries
        RedisAuthError: Credenciais inválidas
        RedisTimeoutError: Timeout persistente
    """

    # Validar configuração
    if not settings.REDIS_URL:
        logger.critical("redis_url_missing")
        raise ConfigurationError(
            "REDIS_URL não configurado",
            details={"hint": "Adicione REDIS_URL ao arquivo .env"},
        )

    logger.info(
        "redis_initialization_started",
        max_retries=max_retries,
        redis_url=settings.REDIS_URL.split("@")[-1],
    )

    last_error = None

    for attempt in range(max_retries):
        try:
            async with redis_connection_manager() as redis_client:
                # Inicializar idempotency manager
                from resync.api.dependencies import initialize_idempotency_manager

                await initialize_idempotency_manager(redis_client)

                logger.info(
                    "redis_initialized", attempt=attempt + 1, max_retries=max_retries
                )
                return

        except RedisAuthError:
            # Não faz retry em erro de auth
            logger.critical("redis_auth_failed_no_retry")
            raise

        except (RedisConnectionError, RedisTimeoutError) as e:
            last_error = e

            if attempt >= max_retries - 1:
                # Última tentativa falhou
                logger.critical(
                    "redis_initialization_failed", attempts=max_retries, error=str(e)
                )
                raise

            # Calcular backoff exponencial
            backoff = min(max_backoff, base_backoff * (2**attempt))

            logger.warning(
                "redis_retry_attempt",
                attempt=attempt + 1,
                max_retries=max_retries,
                next_retry_seconds=backoff,
                error=str(e),
            )

            await asyncio.sleep(backoff)

        except ResponseError as e:
            error_msg = str(e).upper()

            # Verificar se é erro de autenticação disfarçado
            if "NOAUTH" in error_msg or "WRONGPASS" in error_msg:
                logger.critical("redis_access_denied", error=str(e))
                raise RedisAuthError(
                    "Redis requer autenticação",
                    details={
                        "error": str(e),
                        "hint": "Adicione senha ao REDIS_URL: redis://:senha@localhost:6379",
                    },
                ) from e

            # Outros erros de resposta
            if attempt >= max_retries - 1:
                logger.critical("redis_response_error", error=str(e))
                raise RedisInitializationError(
                    f"Erro Redis: {str(e)}", details={"error": str(e)}
                ) from e

            backoff = min(max_backoff, base_backoff * (2**attempt))
            await asyncio.sleep(backoff)

        except BusyLoadingError as e:
            # Redis ainda carregando
            if attempt >= max_retries - 1:
                logger.critical("redis_busy_loading", error=str(e))
                raise RedisConnectionError(
                    "Redis ocupado carregando dados",
                    details={
                        "error": str(e),
                        "hint": "Aguarde Redis finalizar carga inicial",
                    },
                ) from e

            backoff = min(max_backoff, base_backoff * (2**attempt))
            logger.warning(
                "redis_busy_retry", attempt=attempt + 1, backoff_seconds=backoff
            )
            await asyncio.sleep(backoff)

        except Exception as e:
            # Erro inesperado - fail fast
            logger.critical(
                "redis_unexpected_error", error_type=type(e).__name__, error=str(e)
            )
            raise RedisInitializationError(
                f"Erro inesperado ao inicializar Redis: {type(e).__name__}",
                details={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "hint": "Verifique logs para detalhes",
                },
            ) from e

    # Se chegou aqui, todas as tentativas falharam
    if last_error:
        raise last_error


@asynccontextmanager
async def lifespan_with_improvements(app: FastAPI) -> AsyncIterator[None]:
    """Manage the application lifecycle with improvements."""
    logger.info("starting_application_with_improvements")

    # Startup
    try:
        # Get required services from DI container
        tws_client = await app_container.get(ITWSClient)
        agent_manager = await app_container.get(IAgentManager)
        knowledge_graph = await app_container.get(IKnowledgeGraph)

        # Initialize TWS monitor
        tws_monitor_instance = await get_tws_monitor(tws_client)

        # Setup dependency injection
        setup_dependencies(tws_client, agent_manager, knowledge_graph)

        # Initialize CQRS dispatcher
        initialize_dispatcher(tws_client, tws_monitor_instance)

        # Initialize Redis with improved retry logic
        await initialize_redis_with_retry(
            max_retries=getattr(settings, "redis_max_startup_retries", 3),
            base_backoff=getattr(settings, "redis_startup_backoff_base", 0.1),
            max_backoff=getattr(settings, "redis_startup_backoff_max", 10.0),
        )

        logger.info("application_startup_completed_successfully")

        yield  # Application runs here

    except (
        RedisConnectionError,
        RedisAuthError,
        RedisTimeoutError,
        RedisInitializationError,
    ):
        # Error already logged, propagate to FastAPI
        sys.exit(1)
    except Exception as e:
        logger.critical("failed_to_start_application", error=str(e), exc_info=True)
        raise

    finally:
        # Shutdown
        logger.info("shutting_down_application")

        try:
            await shutdown_tws_monitor()
            logger.info("application_shutdown_completed_successfully")
        except Exception as e:
            logger.error("error_during_shutdown", error=str(e), exc_info=True)
