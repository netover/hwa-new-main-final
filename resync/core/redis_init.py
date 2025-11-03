"""
Redis initialization and connection management.

This module provides Redis client initialization with connection pooling,
distributed locking, health checks, and proper error handling.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from contextlib import suppress

from resync.core.container import app_container  # noqa: C0415
from resync.core.idempotency.manager import IdempotencyManager  # noqa: C0415
from resync.settings import settings

try:  # pragma: no cover
    import redis.asyncio as redis  # type: ignore

    # Import correct Redis exceptions
    from redis.exceptions import (
        AuthenticationError,
        BusyLoadingError,
        RedisError,
    )
    from redis.exceptions import (
        ConnectionError as RedisConnError,
    )
    from redis.exceptions import (
        TimeoutError as RedisTimeoutError,
    )
except ImportError:  # redis opcional
    redis = None  # type: ignore
    RedisError = (
        BusyLoadingError
    ) = AuthenticationError = RedisConnError = RedisTimeoutError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class RedisInitError(RuntimeError):
    """Erro de inicialização do Redis."""


_REDIS_CLIENT: redis.Redis | None = None  # type: ignore


def is_redis_available() -> bool:
    """Check if Redis library is available."""
    return redis is not None


def get_redis_client() -> redis.Redis:  # type: ignore
    """
    Late-accessor. Evita conectar durante a coleta do pytest.
    Respeita RESYNC_DISABLE_REDIS=1 para cenários de teste/coleta.
    """
    if os.getenv("RESYNC_DISABLE_REDIS") == "1":
        raise RuntimeError("Redis disabled by RESYNC_DISABLE_REDIS=1")
    if redis is None:
        raise RuntimeError("redis-py not installed (redis.asyncio).")
    global _REDIS_CLIENT  # pylint: disable=W0603
    if _REDIS_CLIENT is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _REDIS_CLIENT = redis.from_url(
            url, encoding="utf-8", decode_responses=True
        )
        logger.info("Initialized Redis client (lazy).")
    return _REDIS_CLIENT


class RedisInitializer:
    """
    Thread-safe Redis initialization with connection pooling.
    """

    UNLOCK_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("del", KEYS[1])
    else
      return 0
    end
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._initialized = False
        self._client: redis.Redis | None = None  # type: ignore
        self._health_task: asyncio.Task | None = None

    @property
    def initialized(self) -> bool:
        """Retorna se o initializer está inicializado. Para compatibilidade."""
        return self._initialized

    async def initialize(
        self,
        max_retries: int = 3,
        base_backoff: float = 0.1,  # pylint: disable=W0613
        max_backoff: float = 10.0,  # pylint: disable=W0613
        health_check_interval: int = 5,
        fatal_on_fail: bool = False,  # pylint: disable=W0613
        redis_url: str | None = None,
    ) -> redis.Redis:  # type: ignore
        """
        Inicializa cliente Redis com:
        - Lock concorrente
        - Lock distribuído seguro (unlock com verificação)
        - Teste RW consistente
        - Health check em background
        """
        if os.getenv("RESYNC_DISABLE_REDIS") == "1":
            raise RedisInitError("Redis disabled by RESYNC_DISABLE_REDIS=1")
        if redis is None:
            raise RedisInitError("redis-py (redis.asyncio) not installed.")

        async with self._lock:
            if self._initialized and self._client:
                try:
                    await asyncio.wait_for(self._client.ping(), timeout=1.0)
                    return self._client
                except (RedisError, asyncio.TimeoutError):
                    logger.warning(
                        "Existing Redis connection lost, reinitializing"
                    )
                    self._initialized = False

            lock_key = "resync:init:lock"
            lock_val = f"instance-{os.getpid()}"
            lock_timeout = 30  # seconds

            for attempt in range(max_retries):
                try:
                    redis_client = await self._create_client_with_pool(
                        redis_url
                    )

                    acquired = await redis_client.set(
                        lock_key, lock_val, nx=True, ex=lock_timeout
                    )
                    if not acquired:
                        logger.info(
                            "Another instance is initializing Redis, waiting... "
                            "(attempt %s/%s)",
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(2)
                        continue

                    try:
                        # Conectividade básica
                        await asyncio.wait_for(
                            redis_client.ping(), timeout=2.0
                        )

                        # Teste RW coerente com decode_responses=True
                        test_key = f"resync:health:test:{os.getpid()}"
                        await redis_client.set(test_key, "ok", ex=60)
                        test_value = await redis_client.get(test_key)
                        if test_value != "ok":
                            raise RedisInitError(
                                "Redis read/write test failed"
                            )
                        await redis_client.delete(test_key)

                        # Idempotency manager
                        await self._initialize_idempotency(redis_client)

                        self._client = redis_client
                        self._initialized = True

                        logger.info(
                            "Redis initialized successfully",
                            extra={
                                "attempt": attempt + 1,
                                "pool_size": getattr(
                                    redis_client.connection_pool,
                                    "max_connections",
                                    None,
                                ),
                            },
                        )

                        # Health check (encerra se já houver uma task antiga)
                        if self._health_task and not self._health_task.done():
                            self._health_task.cancel()
                            with suppress(asyncio.CancelledError):
                                await self._health_task
                        self._health_task = asyncio.create_task(
                            self._health_check_loop(health_check_interval)
                        )

                        return redis_client

                    finally:
                        # Unlock seguro (só remove se ainda for nosso lock)
                        with suppress(RedisError, ConnectionError):
                            await redis_client.eval(
                                self.UNLOCK_SCRIPT, 1, lock_key, lock_val
                            )

                except AuthenticationError as e:
                    msg = f"Redis authentication failed: {e}"
                    logger.critical(msg)
                    raise RedisInitError(msg) from e

                except Exception as e:  # pylint: disable=W0705
                    msg = "Unexpected error during Redis initialization"
                    logger.critical(msg, exc_info=True)
                    raise RedisInitError(f"{msg}: {e}") from e

        raise RedisInitError(
            "Redis initialization failed - unexpected fallthrough"
        )

    async def _create_client_with_pool(
        self, redis_url: str | None = None
    ) -> redis.Redis:  # type: ignore
        if redis is None:
            raise RedisInitError("redis not installed.")
        keepalive_opts = {}
        # Opções portáveis
        for name in ("TCP_KEEPIDLE", "TCP_KEEPINTVL", "TCP_KEEPCNT"):
            if hasattr(socket, name):
                keepalive_opts[getattr(socket, name)] = {  # type: ignore[arg-type]
                    "TCP_KEEPIDLE": 60,
                    "TCP_KEEPINTVL": 10,
                    "TCP_KEEPCNT": 3,
                }[
                    name
                ]
        # Include a ``socket_timeout`` to prevent hangs on read/write operations.
        # The default timeout can be overridden via settings.redis_socket_timeout.
        return redis.Redis.from_url(
            redis_url or settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=getattr(settings, "redis_max_connections", 50),
            socket_connect_timeout=getattr(
                settings, "redis_socket_connect_timeout", 5
            ),
            # Added socket_timeout to ensure read/write operations fail fast
            socket_timeout=getattr(settings, "redis_socket_timeout", 3),
            socket_keepalive=True,
            socket_keepalive_options=keepalive_opts or None,
            health_check_interval=getattr(
                settings, "redis_health_check_interval", 30
            ),
            retry_on_timeout=True,
            retry_on_error=[
                RedisConnError,
                RedisTimeoutError,
                BusyLoadingError,
            ],
        )

    async def _initialize_idempotency(self, redis_client: redis.Redis) -> None:  # type: ignore
        app_container.register_instance(
            IdempotencyManager, IdempotencyManager(redis_client)
        )

    async def _health_check_loop(self, interval: int) -> None:
        while self._initialized:
            await asyncio.sleep(interval)
            try:
                if self._client:
                    await asyncio.wait_for(self._client.ping(), timeout=2.0)
            except (RedisError, asyncio.TimeoutError):
                logger.error(
                    "Redis health check failed - connection may be lost",
                    exc_info=True,
                )
                self._initialized = False
                break
            except (OSError, ValueError) as e:
                logger.error(
                    "Unexpected error in Redis health check: %s",
                    e,
                    exc_info=True,
                )

    async def close(self) -> None:
        """Close the Redis initializer and cleanup resources."""
        self._initialized = False
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_task
        if self._client:
            with suppress(RedisError, ConnectionError):
                await self._client.close()
            with suppress(RedisError, ConnectionError):
                await self._client.connection_pool.disconnect()


# Global Redis initializer instance - lazy initialization
_redis_initializer: RedisInitializer | None = None


async def get_redis_initializer() -> RedisInitializer:
    """
    Retorna instância global do initializer.
    Nota: se houver alta concorrência de criação, considere um lock.
    """
    global _redis_initializer  # pylint: disable=W0603
    if _redis_initializer is None:
        _redis_initializer = RedisInitializer()
    return _redis_initializer




