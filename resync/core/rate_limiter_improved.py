"""
Implementação Melhorada de Rate Limiting com Token Bucket e Leaky Bucket.

Este módulo fornece algoritmos eficientes de rate limiting para controle de tráfego,
com suporte a concorrência e métricas detalhadas.
"""

import asyncio
import contextlib
import time
from collections import deque
from collections.abc import Callable
from functools import wraps
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TokenBucketRateLimiter:
    """
    Rate limiter usando algoritmo Token Bucket.
    Mais eficiente que sliding window para alta concorrência.
    """

    def __init__(
        self,
        rate: float,  # tokens por segundo
        capacity: int,  # capacidade máxima do bucket
        name: str = "default",
    ):
        self.rate = rate
        self.capacity = capacity
        self.name = name
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

        # Métricas
        self.requests_allowed = 0
        self.requests_denied = 0
        self.tokens_consumed = 0

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Tenta adquirir tokens do bucket.

        Returns:
            True se tokens foram adquiridos, False caso contrário
        """
        async with self._lock:
            now = time.monotonic()

            # Adicionar tokens baseado no tempo decorrido
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Verificar se há tokens suficientes
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.requests_allowed += 1
                self.tokens_consumed += tokens
                return True
            self.requests_denied += 1
            return False

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """Aguarda até poder adquirir tokens."""
        while not await self.acquire(tokens):
            # Calcular tempo de espera baseado na taxa
            needed = tokens - self.tokens
            wait_time = needed / self.rate if self.rate > 0 else 0.1
            await asyncio.sleep(wait_time)

    def decorator(self, tokens: int = 1):
        """Decorator para rate limiting."""

        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def wrapped(*args, **kwargs) -> Any:
                await self.wait_and_acquire(tokens)
                return await func(*args, **kwargs)

            return wrapped

        return wrapper

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do rate limiter."""
        total_requests = self.requests_allowed + self.requests_denied
        success_rate = (
            self.requests_allowed / total_requests if total_requests > 0 else 0
        )

        return {
            "name": self.name,
            "algorithm": "token_bucket",
            "rate": self.rate,
            "capacity": self.capacity,
            "current_tokens": self.tokens,
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "success_rate": success_rate,
            "tokens_consumed": self.tokens_consumed,
            "last_update": self.last_update,
        }


class LeakyBucketRateLimiter:
    """
    Rate limiter usando algoritmo Leaky Bucket.
    Melhor para smoothing de tráfego.
    """

    def __init__(
        self,
        rate: float,  # vazão por segundo
        capacity: int,  # capacidade do bucket
        name: str = "default",
    ):
        self.rate = rate  # vazão por segundo
        self.capacity = capacity
        self.name = name
        self.queue = deque(maxlen=capacity)
        self._lock = asyncio.Lock()
        self._leak_task: asyncio.Task | None = None

        # Métricas
        self.requests_allowed = 0
        self.requests_denied = 0
        self.requests_processed = 0

    async def start(self):
        """Inicia o processo de vazamento."""
        if self._leak_task is None:
            self._leak_task = asyncio.create_task(self._leak())
            logger.info("leaky_bucket_started", name=self.name, rate=self.rate)

    async def stop(self):
        """Para o processo de vazamento."""
        if self._leak_task:
            self._leak_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._leak_task
            self._leak_task = None
            logger.info("leaky_bucket_stopped", name=self.name)

    async def _leak(self):
        """Processo contínuo de vazamento."""
        while True:
            await asyncio.sleep(1 / self.rate)
            async with self._lock:
                if self.queue:
                    self.queue.popleft()
                    self.requests_processed += 1

    async def acquire(self) -> bool:
        """Tenta adicionar requisição ao bucket."""
        async with self._lock:
            if len(self.queue) < self.capacity:
                self.queue.append(time.monotonic())
                self.requests_allowed += 1
                return True
            self.requests_denied += 1
            return False

    async def wait_and_acquire(self) -> None:
        """Aguarda até poder adicionar requisição ao bucket."""
        while not await self.acquire():
            # Espera baseada na taxa de vazamento
            wait_time = 1 / self.rate if self.rate > 0 else 0.1
            await asyncio.sleep(wait_time)

    def decorator(self):
        """Decorator para rate limiting."""

        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def wrapped(*args, **kwargs) -> Any:
                await self.wait_and_acquire()
                return await func(*args, **kwargs)

            return wrapped

        return wrapper

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do rate limiter."""
        total_requests = self.requests_allowed + self.requests_denied
        success_rate = (
            self.requests_allowed / total_requests if total_requests > 0 else 0
        )

        return {
            "name": self.name,
            "algorithm": "leaky_bucket",
            "rate": self.rate,
            "capacity": self.capacity,
            "current_queue_size": len(self.queue),
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "requests_processed": self.requests_processed,
            "success_rate": success_rate,
            "running": self._leak_task is not None,
        }


class SlidingWindowRateLimiter:
    """
    Rate limiter usando sliding window.
    Mais preciso para controle de burst, mas mais complexo.
    """

    def __init__(
        self, requests_per_window: int, window_seconds: float, name: str = "default"
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.name = name
        self.requests = deque()
        self._lock = asyncio.Lock()

        # Métricas
        self.requests_allowed = 0
        self.requests_denied = 0

    async def acquire(self) -> bool:
        """Verifica se requisição pode ser processada."""
        async with self._lock:
            now = time.monotonic()

            # Remove requests fora da janela
            while self.requests and self.requests[0] <= now - self.window_seconds:
                self.requests.popleft()

            # Verifica se pode aceitar nova requisição
            if len(self.requests) < self.requests_per_window:
                self.requests.append(now)
                self.requests_allowed += 1
                return True
            self.requests_denied += 1
            return False

    async def wait_and_acquire(self) -> None:
        """Aguarda até poder processar requisição."""
        while not await self.acquire():
            # Espera até a próxima requisição expirar da janela
            if self.requests:
                wait_time = max(
                    0, (self.requests[0] + self.window_seconds) - time.monotonic()
                )
            else:
                wait_time = 0.1
            await asyncio.sleep(wait_time)

    def decorator(self):
        """Decorator para rate limiting."""

        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def wrapped(*args, **kwargs) -> Any:
                await self.wait_and_acquire()
                return await func(*args, **kwargs)

            return wrapped

        return wrapper

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do rate limiter."""
        total_requests = self.requests_allowed + self.requests_denied
        success_rate = (
            self.requests_allowed / total_requests if total_requests > 0 else 0
        )

        return {
            "name": self.name,
            "algorithm": "sliding_window",
            "requests_per_window": self.requests_per_window,
            "window_seconds": self.window_seconds,
            "current_window_requests": len(self.requests),
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "success_rate": success_rate,
        }


class RateLimiterManager:
    """
    Gerenciador centralizado de rate limiters.
    Permite configuração e monitoramento de múltiplos limiters.
    """

    def __init__(self):
        self.limiters: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def create_token_bucket(
        self, name: str, rate: float, capacity: int
    ) -> TokenBucketRateLimiter:
        """Cria um Token Bucket rate limiter."""
        async with self._lock:
            if name in self.limiters:
                raise ValueError(f"Rate limiter '{name}' already exists")

            limiter = TokenBucketRateLimiter(rate, capacity, name)
            self.limiters[name] = limiter
            logger.info("token_bucket_created", name=name, rate=rate, capacity=capacity)
            return limiter

    async def create_leaky_bucket(
        self, name: str, rate: float, capacity: int
    ) -> LeakyBucketRateLimiter:
        """Cria um Leaky Bucket rate limiter."""
        async with self._lock:
            if name in self.limiters:
                raise ValueError(f"Rate limiter '{name}' already exists")

            limiter = LeakyBucketRateLimiter(rate, capacity, name)
            await limiter.start()
            self.limiters[name] = limiter
            logger.info("leaky_bucket_created", name=name, rate=rate, capacity=capacity)
            return limiter

    async def create_sliding_window(
        self, name: str, requests_per_window: int, window_seconds: float
    ) -> SlidingWindowRateLimiter:
        """Cria um Sliding Window rate limiter."""
        async with self._lock:
            if name in self.limiters:
                raise ValueError(f"Rate limiter '{name}' already exists")

            limiter = SlidingWindowRateLimiter(
                requests_per_window, window_seconds, name
            )
            self.limiters[name] = limiter
            logger.info(
                "sliding_window_created",
                name=name,
                requests_per_window=requests_per_window,
                window_seconds=window_seconds,
            )
            return limiter

    def get_limiter(self, name: str) -> Any:
        """Obtém um rate limiter por nome."""
        if name not in self.limiters:
            raise KeyError(f"Rate limiter '{name}' not found")
        return self.limiters[name]

    async def remove_limiter(self, name: str) -> bool:
        """Remove um rate limiter."""
        async with self._lock:
            if name in self.limiters:
                limiter = self.limiters[name]
                if hasattr(limiter, "stop"):
                    await limiter.stop()
                del self.limiters[name]
                logger.info("rate_limiter_removed", name=name)
                return True
            return False

    def get_all_stats(self) -> dict[str, Any]:
        """Retorna estatísticas de todos os limiters."""
        return {name: limiter.get_stats() for name, limiter in self.limiters.items()}

    async def shutdown(self):
        """Para todos os rate limiters."""
        for limiter in self.limiters.values():
            if hasattr(limiter, "stop"):
                await limiter.stop()
        self.limiters.clear()
        logger.info("rate_limiter_manager_shutdown")


# Instância global do gerenciador
rate_limiter_manager = RateLimiterManager()


# Funções de conveniência para uso direto
async def create_token_bucket_limiter(
    name: str, rate: float, capacity: int
) -> TokenBucketRateLimiter:
    """Cria um Token Bucket limiter global."""
    return await rate_limiter_manager.create_token_bucket(name, rate, capacity)


async def create_leaky_bucket_limiter(
    name: str, rate: float, capacity: int
) -> LeakyBucketRateLimiter:
    """Cria um Leaky Bucket limiter global."""
    return await rate_limiter_manager.create_leaky_bucket(name, rate, capacity)


def get_limiter(name: str) -> Any:
    """Obtém limiter global por nome."""
    return rate_limiter_manager.get_limiter(name)


def rate_limit(name: str, tokens: int = 1):
    """
    Decorator para aplicar rate limiting usando limiter nomeado.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            limiter = get_limiter(name)
            await limiter.wait_and_acquire(tokens)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
