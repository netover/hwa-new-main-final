"""
Testes unitários isolados para métricas do pool de conexões.

Este módulo testa cada métrica individualmente de forma isolada,
usando mocks precisos para simular cenários de sucesso, falha e
concorrência, seguindo melhores práticas de 2025 para testes assíncronos.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from resync.core.pools.base_pool import ConnectionPoolConfig, ConnectionPoolStats
from resync.core.pools.db_pool import DatabaseConnectionPool


class TestPoolMetricsIsolation:
    """Testes unitários isolados para métricas de pool de conexões."""

    @pytest.fixture
    def mock_config(self):
        """Configuração mockada para testes."""
        return ConnectionPoolConfig(
            pool_name="unit_test_pool",
            min_size=1,
            max_size=5,
            connection_timeout=2,
        )

    @pytest.fixture
    async def mock_pool(self, mock_config):
        """Pool mockado com dependências isoladas."""
        pool = DatabaseConnectionPool(mock_config, "sqlite:///:memory:")

        # Mock completo da criação do engine para evitar dependências reais
        pool._async_engine = AsyncMock()

        # Mock do sessionmaker
        mock_session_instance = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.rollback = AsyncMock()

        mock_session_maker_instance = Mock()
        mock_session_maker_instance.return_value = mock_session_instance
        pool._async_sessionmaker = mock_session_maker_instance

        # Inicializar o pool sem dependências reais
        pool._initialized = True
        pool._shutdown = False
        pool.stats = ConnectionPoolStats(pool_name="unit_test_pool")

        yield pool

    @pytest.mark.asyncio
    async def test_increment_active_connections(self, mock_pool):
        """Testa incremento isolado de active_connections."""
        initial_stats = mock_pool.get_stats_copy()

        await mock_pool.increment_stat("active_connections")

        updated_stats = mock_pool.get_stats_copy()
        assert updated_stats["active_connections"] == initial_stats["active_connections"] + 1
        assert updated_stats["pool_name"] == "unit_test_pool"  # Outras métricas inalteradas

    @pytest.mark.asyncio
    async def test_increment_connection_creations_on_success_only(self, mock_pool):
        """Testa que connection_creations incrementa corretamente em conexões bem-sucedidas."""
        initial_stats = mock_pool.get_stats_copy()

        async with mock_pool.get_connection():
            pass  # Simula uso bem-sucedido

        success_stats = mock_pool.get_stats_copy()
        assert success_stats["connection_creations"] == initial_stats["connection_creations"] + 1
        assert success_stats["active_connections"] == initial_stats["active_connections"]  # Deve voltar a zero após uso

        # Verificar que não há vazamentos - active_connections deve ser 0 após uso
        assert success_stats["active_connections"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_copy_returns_immutable_snapshot(self, mock_pool):
        """Testa que get_stats_copy retorna snapshot imutável e consistente."""
        # Capturar estado inicial
        snapshot1 = mock_pool.get_stats_copy()
        assert isinstance(snapshot1, dict)
        assert snapshot1["active_connections"] == 0

        # Modificar stats internamente
        await mock_pool.increment_stat("active_connections")

        # Capturar novo snapshot
        snapshot2 = mock_pool.get_stats_copy()

        # Verificar isolamento: snapshots são independentes
        assert snapshot1["active_connections"] == 0
        assert snapshot2["active_connections"] == 1
        assert snapshot1 is not snapshot2  # Objetos diferentes

        # Verificar que snapshot é mutável (cópia)
        snapshot1_copy = snapshot1.copy()
        snapshot1_copy["active_connections"] = 999
        assert snapshot1["active_connections"] == 0  # Original inalterado
        assert mock_pool.get_stats_copy()["active_connections"] == 1  # Pool inalterado
