"""
Testes para os Migration Managers.
"""

from unittest.mock import AsyncMock

import pytest

from resync.core.migration_managers import (
    CacheMigrationManager,
    RateLimitMigrationManager,
    TWSMigrationManager,
)
from resync.settings import Settings


class TestCacheMigrationManager:
    """Testes para CacheMigrationManager."""

    @pytest.fixture
    async def migration_manager(self):
        """Fixture para migration manager."""
        manager = CacheMigrationManager()
        await manager.initialize()
        yield manager
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_initialization(self, migration_manager):
        """Testa inicialização do manager."""
        assert migration_manager.legacy_cache is not None
        assert migration_manager.new_cache is not None

    @pytest.mark.asyncio
    async def test_legacy_mode(self, migration_manager):
        """Testa modo legacy (use_new_cache=False)."""
        migration_manager.use_new_cache = False

        # Set value
        await migration_manager.set("test_key", "test_value")

        # Get value (deve vir do cache legacy)
        value = await migration_manager.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_new_cache_mode(self, migration_manager):
        """Testa modo new cache."""
        migration_manager.use_new_cache = True

        # Set value (vai para ambos os caches)
        await migration_manager.set("test_key", "test_value")

        # Get value (tenta do novo cache primeiro)
        value = await migration_manager.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, migration_manager):
        """Testa fallback quando novo cache falha."""
        migration_manager.use_new_cache = True

        # Simular erro no novo cache
        original_get = migration_manager.new_cache.get

        async def failing_get(key):
            if key == "failing_key":
                raise Exception("Simulated error")
            return await original_get(key)

        migration_manager.new_cache.get = failing_get

        # Set value no cache legacy
        await migration_manager.legacy_cache.set("failing_key", "legacy_value")

        # Get deve fazer fallback
        value = await migration_manager.get("failing_key")
        assert value == "legacy_value"

        # Restaurar método original
        migration_manager.new_cache.get = original_get

    @pytest.mark.asyncio
    async def test_delete_operation(self, migration_manager):
        """Testa operação de delete."""
        await migration_manager.set("delete_key", "delete_value")

        # Delete deve funcionar em ambos os caches
        result = await migration_manager.delete("delete_key")
        assert result is True

        # Verificar que foi removido
        value = await migration_manager.get("delete_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_clear_operation(self, migration_manager):
        """Testa operação de clear."""
        await migration_manager.set("clear_key1", "value1")
        await migration_manager.set("clear_key2", "value2")

        await migration_manager.clear()

        # Verificar que ambos foram limpos
        assert await migration_manager.get("clear_key1") is None
        assert await migration_manager.get("clear_key2") is None


class TestTWSMigrationManager:
    """Testes para TWSMigrationManager."""

    @pytest.fixture
    async def migration_manager(self):
        """Fixture para TWS migration manager."""
        manager = TWSMigrationManager()
        await manager.initialize()
        yield manager

    @pytest.mark.asyncio
    async def test_initialization(self, migration_manager):
        """Testa inicialização do TWS manager."""
        assert migration_manager.legacy_client is not None
        assert migration_manager.new_client is not None

    @pytest.mark.asyncio
    async def test_legacy_mode(self, migration_manager):
        """Testa modo legacy."""
        migration_manager.use_new_client = False

        # Mock do método connect do legacy client
        migration_manager.legacy_client.connect = AsyncMock(return_value=True)

        result = await migration_manager.connect()
        assert result is True
        migration_manager.legacy_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_client_mode(self, migration_manager):
        """Testa modo new client."""
        migration_manager.use_new_client = True

        # Mock do método connect do new client
        migration_manager.new_client.connect = AsyncMock(return_value=True)

        result = await migration_manager.connect()
        assert result is True
        migration_manager.new_client.connect.assert_called_once()


class TestRateLimitMigrationManager:
    """Testes para RateLimitMigrationManager."""

    @pytest.fixture
    async def migration_manager(self):
        """Fixture para rate limit migration manager."""
        manager = RateLimitMigrationManager()
        await manager.initialize()
        yield manager

    @pytest.mark.asyncio
    async def test_initialization(self, migration_manager):
        """Testa inicialização do rate limit manager."""
        assert migration_manager.new_limiter is not None

    @pytest.mark.asyncio
    async def test_legacy_mode(self, migration_manager):
        """Testa modo legacy (sempre permite)."""
        migration_manager.use_new_limiter = False

        result = await migration_manager.acquire(5)
        assert result is True

    @pytest.mark.asyncio
    async def test_new_limiter_mode(self, migration_manager):
        """Testa modo new limiter."""
        migration_manager.use_new_limiter = True

        # Deve permitir inicialmente
        result = await migration_manager.acquire(5)
        assert result is True

        # Consumir todos os tokens
        for _ in range(4):  # Já usou 1, faltam 4 para lotar
            await migration_manager.acquire(5)

        # Próximo deve falhar
        result = await migration_manager.acquire(1)
        assert result is False

    @pytest.mark.asyncio
    async def test_stats(self, migration_manager):
        """Testa obtenção de estatísticas."""
        await migration_manager.acquire()

        stats = migration_manager.get_stats()
        assert "migration_mode" in stats
        assert "new_limiter_stats" in stats


@pytest.mark.asyncio
async def test_migration_managers_integration():
    """Testa integração entre os migration managers."""
    from resync.core.migration_managers import (
        cache_migration_manager,
        initialize_migration_managers,
        rate_limit_migration_manager,
        shutdown_migration_managers,
        tws_migration_manager,
    )

    try:
        # Inicializar
        await initialize_migration_managers()

        # Testar cache
        await cache_migration_manager.set("integration_test", "test_value")
        value = await cache_migration_manager.get("integration_test")
        assert value == "test_value"

        # Testar rate limiting
        allowed = await rate_limit_migration_manager.acquire()
        assert allowed is True

        # Testar TWS (simulado)
        tws_migration_manager.use_new_client = True

    finally:
        # Cleanup
        await shutdown_migration_managers()


def test_settings_migration_flags():
    """Testa que as feature flags de migração estão definidas."""
    settings = Settings()

    # Verificar que as flags existem
    assert hasattr(settings, "MIGRATION_USE_NEW_CACHE")
    assert hasattr(settings, "MIGRATION_USE_NEW_TWS")
    assert hasattr(settings, "MIGRATION_USE_NEW_RATE_LIMIT")
    assert hasattr(settings, "MIGRATION_ENABLE_METRICS")

    # Verificar valores padrão
    assert settings.MIGRATION_USE_NEW_CACHE is False
    assert settings.MIGRATION_USE_NEW_TWS is False
    assert settings.MIGRATION_USE_NEW_RATE_LIMIT is False
    assert settings.MIGRATION_ENABLE_METRICS is True
