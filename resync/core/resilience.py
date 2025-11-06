"""
Resiliência Patterns para o Sistema Resync

Este módulo implementa padrões de resiliência para garantir alta disponibilidade
e tolerância a falhas no sistema Resync, incluindo Circuit Breaker, Exponential
Backoff com Jitter e Timeouts configuráveis.

Padrões implementados:
- Circuit Breaker: Previne falhas em cascata
- Exponential Backoff: Retry inteligente com backoff exponencial
- Timeout Manager: Controle de timeouts para operações
- Decoradores: Aplicação fácil dos padrões

Author: Resync Team
Date: October 2025
"""

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar, Iterable

from resync.core.exceptions import CircuitBreakerError
from resync.core.structured_logger import get_logger
import pybreaker

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Estados possíveis do Circuit Breaker"""

    CLOSED = "closed"  # Funcionando normalmente
    OPEN = "open"  # Bloqueando chamadas
    HALF_OPEN = "half_open"  # Testando recuperação


@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker"""

    failure_threshold: int = 5
    recovery_timeout: int = 60  # segundos
    expected_exception: type = Exception
    name: str = "default"


@dataclass
class CircuitBreakerMetrics:
    """Métricas do Circuit Breaker"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0


class CircuitBreaker:
    """
    Implementação do Circuit Breaker Pattern

    O Circuit Breaker previne que um sistema continue tentando operações
    que provavelmente vão falhar, permitindo recuperação gradual.
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()

        # Properties for compatibility with tests
        self.fail_max = config.failure_threshold
        self.timeout_duration = timedelta(seconds=config.recovery_timeout)
        self.exclude = config.expected_exception

        logger.info(
            "Circuit breaker initialized",
            name=config.name,
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
        )

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Executa função através do circuit breaker

        Args:
            func: Função assíncrona a ser executada
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função

        Raises:
            CircuitBreakerError: Quando circuit breaker está aberto
            Exception: Exceções originais da função
        """
        async with self._lock:
            self.metrics.total_calls += 1

            if self.state == CircuitBreakerState.OPEN:
                if not self._should_attempt_reset():
                    logger.warning(
                        "Circuit breaker is OPEN, blocking call",
                        name=self.config.name,
                        calls_blocked=self.metrics.total_calls,
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.config.name}' is OPEN"
                    )
                else:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.metrics.state_changes += 1
                    logger.info(
                        "Circuit breaker transitioning to HALF_OPEN",
                        name=self.config.name,
                    )

        try:
            result = await func(*args, **kwargs)

            async with self._lock:
                await self._on_success()

            return result

        except self.config.expected_exception as e:
            async with self._lock:
                logger.debug(
                    "Circuit breaker failure caught",
                    name=self.config.name,
                    exception_type=type(e).__name__,
                    consecutive_failures_before=self.metrics.consecutive_failures,
                )
                await self._on_failure()
                logger.debug(
                    "Circuit breaker failure processed",
                    name=self.config.name,
                    consecutive_failures_after=self.metrics.consecutive_failures,
                    state=self.state.value,
                )

            raise e

    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuit breaker"""
        if self.metrics.last_failure_time is None:
            return True

        elapsed = (datetime.utcnow() - self.metrics.last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout

    async def _on_success(self) -> None:
        """Callback para sucesso"""
        self.metrics.successful_calls += 1
        self.metrics.consecutive_failures = 0
        self.metrics.last_success_time = datetime.utcnow()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.metrics.state_changes += 1
            logger.info(
                "Circuit breaker reset to CLOSED after successful test",
                name=self.config.name,
            )

    async def _on_failure(self) -> None:
        """Callback para falha"""
        self.metrics.failed_calls += 1
        self.metrics.consecutive_failures += 1
        self.metrics.last_failure_time = datetime.utcnow()

        if self.metrics.consecutive_failures >= self.config.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                self.state = CircuitBreakerState.OPEN
                self.metrics.state_changes += 1
                logger.error(
                    "Circuit breaker opened due to consecutive failures",
                    name=self.config.name,
                    failures=self.metrics.consecutive_failures,
                    threshold=self.config.failure_threshold,
                )

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas atuais do circuit breaker"""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "consecutive_failures": self.metrics.consecutive_failures,
            "success_rate": (
                self.metrics.successful_calls / self.metrics.total_calls
                if self.metrics.total_calls > 0
                else 0
            ),
            "last_failure_time": (
                self.metrics.last_failure_time.isoformat()
                if self.metrics.last_failure_time
                else None
            ),
            "last_success_time": (
                self.metrics.last_success_time.isoformat()
                if self.metrics.last_success_time
                else None
            ),
            "state_changes": self.metrics.state_changes,
        }


@dataclass
class RetryConfig:
    """Configuração para retry com backoff"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    expected_exceptions: tuple = (Exception,)


@dataclass
class RetryMetrics:
    """Métricas de retry"""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retry_delay: float = 0.0


class RetryWithBackoff:
    """
    Implementação de Exponential Backoff com Jitter

    Permite retry automático de operações com backoff exponencial
    e jitter para evitar thundering herd.
    """

    def __init__(self, config: RetryConfig):
        self.config = config
        self.metrics = RetryMetrics()

    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Executa função com retry automático

        Args:
            func: Função assíncrona a ser executada
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função

        Raises:
            Exception: Última exceção encontrada
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                self.metrics.total_attempts += 1

                result = await func(*args, **kwargs)

                self.metrics.successful_attempts += 1

                if attempt > 0:
                    logger.info(
                        "Operation succeeded after retry",
                        attempt=attempt,
                        max_retries=self.config.max_retries,
                    )

                return result

            except self.config.expected_exceptions as e:
                last_exception = e

                if attempt == self.config.max_retries:
                    self.metrics.failed_attempts += 1
                    logger.error(
                        "Operation failed after all retry attempts",
                        attempts=attempt + 1,
                        max_retries=self.config.max_retries,
                        error=str(e),
                    )
                    raise e

                # Calcular delay com backoff exponencial
                delay = min(
                    self.config.base_delay * (self.config.exponential_base**attempt),
                    self.config.max_delay,
                )

                # Adicionar jitter para evitar thundering herd
                if self.config.jitter:
                    delay = delay * (0.5 + random.random() * 0.5)

                self.metrics.total_retry_delay += delay

                logger.warning(
                    "Operation failed, retrying with backoff",
                    attempt=attempt + 1,
                    max_retries=self.config.max_retries,
                    delay=delay,
                    error=str(e),
                )

                await asyncio.sleep(delay)

        # Nunca deveria chegar aqui, mas por segurança
        raise last_exception

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de retry"""
        return {
            "total_attempts": self.metrics.total_attempts,
            "successful_attempts": self.metrics.successful_attempts,
            "failed_attempts": self.metrics.failed_attempts,
            "success_rate": (
                self.metrics.successful_attempts / self.metrics.total_attempts
                if self.metrics.total_attempts > 0
                else 0
            ),
            "average_retry_delay": (
                self.metrics.total_retry_delay
                / (self.metrics.total_attempts - self.metrics.successful_attempts)
                if self.metrics.total_attempts > self.metrics.successful_attempts
                else 0
            ),
        }


class TimeoutManager:
    """
    Gerenciador de timeouts para operações assíncronas
    """

    @staticmethod
    async def with_timeout(
        coro: Awaitable[T],
        timeout_seconds: float,
        timeout_exception: Optional[Exception] = None,
    ) -> T:
        """
        Executa coroutine com timeout

        Args:
            coro: Coroutine a ser executada
            timeout_seconds: Timeout em segundos
            timeout_exception: Exceção customizada para timeout (opcional)

        Returns:
            Resultado da coroutine

        Raises:
            TimeoutError: Quando timeout é excedido
            Exception: Exceção customizada se fornecida
        """
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            if timeout_exception:
                raise timeout_exception from exc
            raise TimeoutError(
                f"Operation timed out after {timeout_seconds} seconds"
            ) from exc


# Decoradores para facilitar uso dos padrões


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: str = None,
):
    """
    Decorador para aplicar Circuit Breaker

    Args:
        failure_threshold: Número de falhas consecutivas para abrir circuit
        recovery_timeout: Tempo em segundos para tentar recuperação
        expected_exception: Tipo de exceção que conta como falha
        name: Nome do circuit breaker (padrão: nome da função)
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        circuit_name = name or f"{func.__module__}.{func.__name__}"
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=circuit_name,
        )
        breaker = CircuitBreaker(config)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await breaker.call(func, *args, **kwargs)

        # Expor circuit breaker para monitoramento
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    expected_exceptions: tuple = (Exception,),
):
    """
    Decorador para aplicar retry com exponential backoff

    Args:
        max_retries: Número máximo de tentativas
        base_delay: Delay base em segundos
        max_delay: Delay máximo em segundos
        exponential_base: Base para crescimento exponencial
        jitter: Se deve adicionar jitter ao delay
        expected_exceptions: Tipos de exceção que devem ser retentados
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            expected_exceptions=expected_exceptions,
        )
        retry = RetryWithBackoff(config)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry.execute(func, *args, **kwargs)

        # Expor retry handler para monitoramento
        wrapper.retry_handler = retry
        return wrapper

    return decorator


def with_timeout(timeout_seconds: float, timeout_exception: Optional[Exception] = None):
    """
    Decorador para aplicar timeout

    Args:
        timeout_seconds: Timeout em segundos
        timeout_exception: Exceção customizada para timeout
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await TimeoutManager.with_timeout(
                func(*args, **kwargs), timeout_seconds, timeout_exception
            )

        return wrapper

    return decorator


# Funções utilitárias para monitoramento


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """
    Retorna todos os circuit breakers registrados

    Nota: Esta função encontra circuit breakers através de inspeção,
    funciona apenas para circuit breakers criados via decoradores.
    """
    import gc

    breakers = {}

    for obj in gc.get_objects():
        if isinstance(obj, CircuitBreaker):
            breakers[obj.config.name] = obj

    return breakers


def get_circuit_breaker_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Retorna métricas de todos os circuit breakers
    """
    breakers = get_all_circuit_breakers()
    return {name: breaker.get_metrics() for name, breaker in breakers.items()}


# Configurações padrão para diferentes tipos de serviço

DEFAULT_HTTP_CONFIG = CircuitBreakerConfig(
    failure_threshold=3, recovery_timeout=30, name="http_service"
)

DEFAULT_DATABASE_CONFIG = CircuitBreakerConfig(
    failure_threshold=5, recovery_timeout=60, name="database_service"
)

DEFAULT_EXTERNAL_API_CONFIG = CircuitBreakerConfig(
    failure_threshold=2, recovery_timeout=120, name="external_api"
)


class CircuitBreakerManager:
    """
    Registry-based Circuit Breaker manager (client-side), inspired by Resilience4j's registry.
    """

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}

    def register(
        self,
        name: str,
        *,
        fail_max: int = 5,
        reset_timeout: int = 60,
        exclude: tuple[type[BaseException], ...] = (),
    ) -> CircuitBreaker:
        if name not in self._breakers:
            config = CircuitBreakerConfig(
                failure_threshold=fail_max,
                recovery_timeout=reset_timeout,
                expected_exception=Exception,
                name=name,
            )
            self._breakers[name] = CircuitBreaker(config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker:
        br = self._breakers.get(name)
        if not br:
            raise KeyError(f"Circuit breaker '{name}' not registered")
        return br

    async def call(
        self, name: str, func: Callable[..., Awaitable[T]], *args, **kwargs
    ) -> T:
        br = self.get(name)
        return await br.call(func, *args, **kwargs)

    def state(self, name: str) -> str:
        state = self.get(name).state
        return state.value  # "closed" | "open" | "half-open"


class CircuitBreakerError(pybreaker.CircuitBreakerError):  # re-export for app
    pass


async def retry_with_backoff_async(
    op: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
    cap: float = 5.0,
    jitter: bool = True,
    retry_on: Iterable[type[BaseException]] = (Exception,),
) -> T:
    """
    AWS guidance: exponential backoff + jitter + cap.
    """
    attempt = 0
    while True:
        try:
            return await op()
        except tuple(retry_on) as e:
            attempt += 1
            if attempt > retries:
                raise
            delay = min(cap, base_delay * (2 ** (attempt - 1)))
            if jitter:
                # full jitter
                delay = random.uniform(0, delay)
            logger.warning(
                "retry attempt=%s delay=%.3fs err=%s", attempt, delay, type(e).__name__
            )
            await asyncio.sleep(delay)
