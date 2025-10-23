"""
Testes para o sistema de cache melhorado.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock

from resync.core.improved_cache import (
    ImprovedAsyncCache,
    CacheEntry,
    InMemoryCacheStorage,
    CacheMetricsCollector,
    CacheTTLManager,
)


class TestCacheEntry:
    """Testes para CacheEntry."""

    def test_cache_entry_creation(self):
        """Testa criação básica de entrada."""
        entry = CacheEntry(value="test", ttl=60)
        assert entry.value == "test"
        assert entry.ttl == 60
        assert entry.access_count == 0

    def test_cache_entry_touch(self):
        """Testa atualização de estatísticas."""
        entry = CacheEntry(value="test")
        initial_access = entry.last_accessed

        time.sleep(0.01)  # Pequena pausa
        entry.touch()

        assert entry.access_count == 1
        assert entry.last_accessed > initial_access

    def test_cache_entry_expiration(self):
        """Testa verificação de expiração."""
        # Entrada sem TTL nunca expira
        entry = CacheEntry(value="test")
        assert not entry.is_expired()

        # Entrada com TTL futuro não expira
        entry = CacheEntry(value="test", ttl=60)
        assert not entry.is_expired()

        # Entrada com TTL passado expira
        entry = CacheEntry(value="test", ttl=-1)
        assert entry.is_expired()


class TestInMemoryCacheStorage:
    """Testes para InMemoryCacheStorage."""

    @pytest.fixture
    async def storage(self):
        """Fixture para storage."""
        storage = InMemoryCacheStorage(num_shards=4)
        yield storage
        # Cleanup
        await storage.clear()

    @pytest.mark.asyncio
    async def test_storage_set_get(self, storage):
        """Testa set e get básicos."""
        await storage.set("key1", "value1")
        value = await storage.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_storage_delete(self, storage):
        """Testa delete."""
        await storage.set("key1", "value1")
        assert await storage.delete("key1") is True
        assert await storage.get("key1") is None
        assert await storage.delete("key1") is False

    @pytest.mark.asyncio
    async def test_storage_clear(self, storage):
        """Testa clear."""
        await storage.set("key1", "value1")
        await storage.set("key2", "value2")
        await storage.clear()

        assert await storage.get("key1") is None
        assert await storage.get("key2") is None

    @pytest.mark.asyncio
    async def test_storage_keys(self, storage):
        """Testa listagem de keys."""
        await storage.set("key1", "value1")
        await storage.set("key2", "value2")

        keys = await storage.keys()
        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys


class TestCacheMetricsCollector:
    """Testes para CacheMetricsCollector."""

    @pytest.fixture
    async def metrics(self):
        """Fixture para metrics collector."""
        return CacheMetricsCollector()

    @pytest.mark.asyncio
    async def test_metrics_recording(self, metrics):
        """Testa gravação de métricas."""
        await metrics.record_hit()
        await metrics.record_hit()
        await metrics.record_miss()
        await metrics.record_set()
        await metrics.record_delete()

        metrics_data = await metrics.get_metrics()
        assert metrics_data["hits"] == 2
        assert metrics_data["misses"] == 1
        assert metrics_data["sets"] == 1
        assert metrics_data["deletes"] == 1
        assert metrics_data["hit_rate"] == 2 / 3

    @pytest.mark.asyncio
    async def test_metrics_hit_rate_calculation(self, metrics):
        """Testa cálculo de hit rate."""
        # Sem requests
        metrics_data = await metrics.get_metrics()
        assert metrics_data["hit_rate"] == 0

        # Apenas misses
        await metrics.record_miss()
        await metrics.record_miss()
        metrics_data = await metrics.get_metrics()
        assert metrics_data["hit_rate"] == 0

        # Mix de hits e misses
        await metrics.record_hit()
        await metrics.record_hit()
        metrics_data = await metrics.get_metrics()
        assert metrics_data["hit_rate"] == 2 / 3


class TestImprovedAsyncCache:
    """Testes para ImprovedAsyncCache."""

    @pytest.fixture
    async def cache(self):
        """Fixture para cache."""
        cache = ImprovedAsyncCache(default_ttl=1)  # TTL curto para testes
        await cache.initialize()
        yield cache
        await cache.shutdown()

    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, cache):
        """Testa operações básicas do cache."""
        # Set e get
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"

        # Delete
        assert await cache.delete("key1") is True
        assert await cache.get("key1") is None

        # Has key
        await cache.set("key2", "value2")
        assert await cache.has_key("key2") is True
        assert await cache.has_key("key3") is False

    @pytest.mark.asyncio
    async def test_cache_ttl(self, cache):
        """Testa funcionalidade de TTL."""
        await cache.set("key1", "value1", ttl=0.1)  # Expira em 100ms

        # Deve existir imediatamente
        assert await cache.get("key1") == "value1"

        # Espera expiração
        await asyncio.sleep(0.2)

        # Deve ter expirado
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_cache_metrics(self, cache):
        """Testa coleta de métricas."""
        # Operações que geram métricas
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss
        await cache.delete("key1")

        metrics = await cache.get_metrics()
        assert metrics["sets"] == 1
        assert metrics["hits"] == 1
        assert metrics["misses"] == 1
        assert metrics["deletes"] == 1

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """Testa estatísticas completas."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        stats = await cache.get_stats()
        assert stats["total_keys"] == 2
        assert stats["initialized"] is True
        assert "hits" in stats
        assert "misses" in stats

    @pytest.mark.asyncio
    async def test_cache_clear(self, cache):
        """Testa limpeza completa do cache."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        assert await cache.has_key("key1") is True
        assert await cache.has_key("key2") is True

        await cache.clear()

        assert await cache.has_key("key1") is False
        assert await cache.has_key("key2") is False


class TestCacheTTLManager:
    """Testes para CacheTTLManager."""

    @pytest.fixture
    async def ttl_manager(self):
        """Fixture para TTL manager."""
        return CacheTTLManager(cleanup_interval=0.1)  # Cleanup rápido para testes

    @pytest.fixture
    async def mock_storage(self):
        """Fixture para storage mock."""
        storage = AsyncMock()
        storage.keys.return_value = ["key1", "key2"]
        storage.get.side_effect = lambda key: None if key == "expired" else "value"
        return storage

    @pytest.mark.asyncio
    async def test_ttl_manager_cleanup_task(self, ttl_manager, mock_storage):
        """Testa tarefa de limpeza periódica."""
        await ttl_manager.start_cleanup_task(mock_storage)

        # Espera algumas execuções do cleanup
        await asyncio.sleep(0.3)

        # Verifica que o cleanup foi chamado
        assert mock_storage.keys.called

        # Para o cleanup
        await ttl_manager.stop_cleanup_task()

        # Verifica que a tarefa foi parada
        assert ttl_manager._cleanup_task is None
