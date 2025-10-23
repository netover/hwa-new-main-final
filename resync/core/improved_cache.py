"""
Sistema de Cache Assíncrono Melhorado com Separação de Responsabilidades.

Este módulo implementa um cache TTL assíncrono seguindo os princípios SOLID:
- Single Responsibility: Cada classe tem uma responsabilidade clara
- Open/Closed: Extensível sem modificar código existente
- Liskov Substitution: Interfaces bem definidas
- Interface Segregation: Interfaces específicas para cada necessidade
- Dependency Inversion: Dependências de abstrações, não concretas
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Entrada individual do cache com metadados."""

    value: T
    created_at: float = field(default_factory=time.time)
    ttl: Optional[float] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Verifica se a entrada expirou."""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)

    def touch(self) -> None:
        """Atualiza estatísticas de acesso."""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheStorage(ABC):
    """Interface abstrata para armazenamento de cache."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Recupera valor do storage."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Armazena valor no storage."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove valor do storage."""

    @abstractmethod
    async def clear(self) -> None:
        """Limpa todo o storage."""

    @abstractmethod
    async def keys(self) -> list[str]:
        """Retorna todas as chaves no storage."""


class InMemoryCacheStorage(CacheStorage):
    """Implementação em memória do storage de cache."""

    def __init__(self, num_shards: int = 16):
        self.num_shards = num_shards
        self.shards: list[dict[str, CacheEntry]] = [{} for _ in range(num_shards)]
        self.locks = [asyncio.Lock() for _ in range(num_shards)]

    def _get_shard(self, key: str) -> tuple[dict, asyncio.Lock]:
        """Retorna shard e lock para uma chave."""
        shard_id = hash(key) % self.num_shards
        return self.shards[shard_id], self.locks[shard_id]

    async def get(self, key: str) -> Optional[Any]:
        """Recupera valor com verificação de TTL."""
        shard, lock = self._get_shard(key)

        async with lock:
            entry = shard.get(key)
            if entry is None:
                return None

            if entry.is_expired():
                del shard[key]
                return None

            entry.touch()
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Armazena valor com TTL opcional."""
        shard, lock = self._get_shard(key)

        async with lock:
            shard[key] = CacheEntry(value=value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        """Remove entrada do cache."""
        shard, lock = self._get_shard(key)

        async with lock:
            if key in shard:
                del shard[key]
                return True
            return False

    async def clear(self) -> None:
        """Limpa todos os shards."""
        for shard, lock in zip(self.shards, self.locks):
            async with lock:
                shard.clear()

    async def keys(self) -> list[str]:
        """Retorna todas as chaves ativas (não expiradas)."""
        all_keys = []
        for shard, lock in zip(self.shards, self.locks):
            async with lock:
                # Filtrar apenas chaves não expiradas
                for key, entry in shard.items():
                    if not entry.is_expired():
                        all_keys.append(key)
        return all_keys


class CacheTTLManager:
    """Gerencia expiração de itens no cache."""

    def __init__(self, cleanup_interval: float = 60.0):
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stop_cleanup = False

    async def start_cleanup_task(self, storage: CacheStorage) -> None:
        """Inicia tarefa de limpeza periódica."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup(storage))
            logger.info("cache_ttl_cleanup_started", interval=self.cleanup_interval)

    async def stop_cleanup_task(self) -> None:
        """Para tarefa de limpeza."""
        self._stop_cleanup = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("cache_ttl_cleanup_stopped")

    async def _periodic_cleanup(self, storage: CacheStorage) -> None:
        """Executa limpeza periódica de itens expirados."""
        while not self._stop_cleanup:
            try:
                await self._cleanup_expired_entries(storage)
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error("cache_cleanup_error", error=str(e))
                await asyncio.sleep(self.cleanup_interval)

    async def _cleanup_expired_entries(self, storage: CacheStorage) -> None:
        """Remove entradas expiradas do storage."""
        keys = await storage.keys()
        expired_count = 0

        for key in keys:
            # O método get já verifica expiração internamente
            value = await storage.get(key)
            if value is None:
                expired_count += 1

        if expired_count > 0:
            logger.debug("cache_expired_entries_cleaned", count=expired_count)


class CacheMetricsCollector:
    """Coletor de métricas para o cache."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        self._lock = asyncio.Lock()

    async def record_hit(self) -> None:
        async with self._lock:
            self.hits += 1

    async def record_miss(self) -> None:
        async with self._lock:
            self.misses += 1

    async def record_set(self) -> None:
        async with self._lock:
            self.sets += 1

    async def record_delete(self) -> None:
        async with self._lock:
            self.deletes += 1

    async def record_eviction(self) -> None:
        async with self._lock:
            self.evictions += 1

    async def get_metrics(self) -> dict:
        """Retorna métricas atuais."""
        async with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0

            return {
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "deletes": self.deletes,
                "evictions": self.evictions,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
            }


class ImprovedAsyncCache:
    """
    Cache assíncrono melhorado com separação de responsabilidades.
    """

    def __init__(
        self,
        storage: Optional[CacheStorage] = None,
        default_ttl: float = 3600,
        max_size: Optional[int] = None,
        cleanup_interval: float = 60.0,
        enable_metrics: bool = True,
    ):
        self.storage = storage or InMemoryCacheStorage()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.enable_metrics = enable_metrics

        # Componentes especializados
        self.ttl_manager = CacheTTLManager(cleanup_interval)
        self.metrics = CacheMetricsCollector() if enable_metrics else None

        # Controle de inicialização
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Inicializa o cache e seus componentes."""
        async with self._init_lock:
            if not self._initialized:
                await self.ttl_manager.start_cleanup_task(self.storage)
                self._initialized = True
                logger.info("improved_cache_initialized")

    async def shutdown(self) -> None:
        """Desliga o cache e seus componentes."""
        await self.ttl_manager.stop_cleanup_task()
        self._initialized = False
        logger.info("improved_cache_shutdown")

    async def get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache."""
        value = await self.storage.get(key)

        if self.metrics:
            if value is None:
                await self.metrics.record_miss()
            else:
                await self.metrics.record_hit()

        return value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Armazena valor no cache."""
        effective_ttl = ttl or self.default_ttl
        await self.storage.set(key, value, effective_ttl)

        if self.metrics:
            await self.metrics.record_set()

    async def delete(self, key: str) -> bool:
        """Remove valor do cache."""
        result = await self.storage.delete(key)

        if self.metrics and result:
            await self.metrics.record_delete()

        return result

    async def clear(self) -> None:
        """Limpa todo o cache."""
        await self.storage.clear()

    async def has_key(self, key: str) -> bool:
        """Verifica se chave existe no cache."""
        value = await self.get(key)
        return value is not None

    async def get_metrics(self) -> dict:
        """Retorna métricas do cache."""
        if self.metrics:
            return await self.metrics.get_metrics()
        return {}

    async def get_keys(self) -> list[str]:
        """Retorna todas as chaves ativas no cache."""
        return await self.storage.keys()

    async def keys(self) -> list[str]:
        """Alias para get_keys() para compatibilidade com testes existentes."""
        return await self.get_keys()

    async def get_stats(self) -> dict:
        """Retorna estatísticas completas do cache."""
        keys = await self.get_keys()
        metrics = await self.get_metrics()

        return {
            "total_keys": len(keys),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "initialized": self._initialized,
            "metrics_enabled": self.metrics is not None,
            **metrics,
        }
