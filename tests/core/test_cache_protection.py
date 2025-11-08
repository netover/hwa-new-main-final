from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from resync.core.cache_with_stampede_protection import (
    CacheEntry,
    CacheWithStampedeProtection,
)


class TestCacheWithStampedeProtection:
    """Testes para o CacheWithStampedeProtection."""

    @pytest.fixture
    def cache(self):
        """Fixture para criar uma instância do cache."""
        # Usar um Redis mock
        redis_client = MagicMock()
        return CacheWithStampedeProtection(redis_client, None)

    def test_cache_entry(self):
        """Testar a classe CacheEntry."""
        entry = CacheEntry(
            value="test_value",
            cached_at=datetime(2025, 10, 9, 12, 0, 0),
            fresh_until=datetime(2025, 10, 9, 12, 5, 0),
            stale_until=datetime(2025, 10, 9, 12, 10, 0),
        )

        assert entry.is_stale()
        assert entry.is_stale_but_usable()
        assert not entry.is_expired()

    @pytest.mark.asyncio
    async def test_get_or_compute(self, cache, event_loop):
        """Testar o método get_or_compute."""
        # Simular cache miss
        cache.redis.get = MagicMock(return_value=None)

        result = await cache.get_or_compute(
            key="test_key",
            compute_fn=lambda: "computed_value",
            ttl=timedelta(seconds=10),
            stale_ttl=timedelta(seconds=20),
        )

        assert result == "computed_value"

    @pytest.mark.asyncio
    async def test_cache_stale_while_revalidate(self, cache, event_loop):
        """Testar comportamento de stale-while-revalidate."""
        # Simular entrada no cache mas expirada
        entry = CacheEntry(
            value="stale_value",
            cached_at=datetime(2025, 10, 9, 12, 0, 0),
            fresh_until=datetime(2025, 10, 9, 12, 0, 0),  # Já expirou
            stale_until=datetime(2025, 10, 9, 12, 5, 0),
        )

        cache._get_cache_entry = MagicMock(return_value=entry)

        result = await cache.get_or_compute(
            key="stale_key",
            compute_fn=lambda: "new_value",
            ttl=timedelta(seconds=10),
            stale_ttl=timedelta(seconds=20),
        )

        assert result == "stale_value"

        # Verificar que compute_fn foi chamada em background
        assert cache._refresh_cache.call_count == 1
