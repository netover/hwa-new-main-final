"""
Testes básicos para ImprovedAsyncCache.
"""

from __future__ import annotations

import asyncio
import pytest
from resync.core.improved_cache import ImprovedAsyncCache  # type: ignore[attr-defined]


class TestImprovedAsyncCache:
    """Testes básicos para ImprovedAsyncCache."""

    @pytest.fixture
    async def cache(self) -> ImprovedAsyncCache:
        """Fixture para cache."""
        cache = ImprovedAsyncCache(default_ttl=60, enable_metrics=True)
        await cache.initialize()  # type: ignore[no-untyped-call]
        yield cache
        await cache.shutdown()  # type: ignore[no-untyped-call]

    @pytest.mark.asyncio
    async def test_basic_operations(self, cache: ImprovedAsyncCache) -> None:
        """Testa operações básicas."""
        # Set
        await cache.set("key1", "value1")  # type: ignore[no-untyped-call]
        await cache.set("key2", "value2", ttl=30)  # type: ignore[no-untyped-call]

        # Get
        value1 = await cache.get("key1")  # type: ignore[no-untyped-call]
        value2 = await cache.get("key2")  # type: ignore[no-untyped-call]

        assert value1 == "value1"
        assert value2 == "value2"

    @pytest.mark.asyncio
    async def test_delete_operation(self, cache: ImprovedAsyncCache) -> None:
        """Testa operação de delete."""
        await cache.set("delete_key", "delete_value")
        value = await cache.get("delete_key")
        assert value == "delete_value"

        # Delete
        deleted = await cache.delete("delete_key")
        assert deleted is True

        # Verificar remoção
        value = await cache.get("delete_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_clear_operation(self, cache: ImprovedAsyncCache) -> None:
        """Testa operação de clear."""
        await cache.set("clear1", "value1")
        await cache.set("clear2", "value2")

        # Clear
        await cache.clear()

        # Verificar remoção
        assert await cache.get("clear1") is None
        assert await cache.get("clear2") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache: ImprovedAsyncCache) -> None:
        """Testa expiração por TTL."""
        await cache.set("ttl_key", "ttl_value", ttl=1)

        # Deve existir imediatamente
        value = await cache.get("ttl_key")
        assert value == "ttl_value"

        # Aguardar expiração
        await asyncio.sleep(1.1)

        # Deve ter expirado
        value = await cache.get("ttl_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_keys_operation(self, cache: ImprovedAsyncCache) -> None:
        """Testa operação keys."""
        await cache.set("keys1", "value1")
        await cache.set("keys2", "value2")
        await cache.set("keys3", "value3")

        keys = await cache.keys()
        assert len(keys) == 3
        assert "keys1" in keys
        assert "keys2" in keys
        assert "keys3" in keys

    @pytest.mark.asyncio
    async def test_stats_operation(self, cache: ImprovedAsyncCache) -> None:
        """Testa coleta de estatísticas."""
        await cache.set("stats_key", "stats_value")

        stats = await cache.get_stats()
        assert isinstance(stats, dict)
        assert "total_keys" in stats
        assert "hits" in stats
        assert "misses" in stats

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache: ImprovedAsyncCache) -> None:
        """Testa acesso concorrente."""

        async def worker(worker_id: int) -> None:
            for i in range(10):
                key = f"worker_{worker_id}_{i}"
                await cache.set(key, f"value_{worker_id}_{i}")
                value = await cache.get(key)
                assert value == f"value_{worker_id}_{i}"

        # Executar 5 workers concorrentes
        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verificar que todos os valores estão lá
        keys = await cache.keys()  # type: ignore[no-untyped-call]
        assert len(keys) == 50  # 5 workers * 10 operações cada


if __name__ == "__main__":
    # Executar testes diretamente
    asyncio.run(
        asyncio.gather(
            TestImprovedAsyncCache().test_basic_operations(
                ImprovedAsyncCache(default_ttl=60, enable_metrics=True)
            )
        )
    )
    print("Testes básicos executados com sucesso!")
