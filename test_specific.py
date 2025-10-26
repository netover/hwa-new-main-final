#!/usr/bin/env python3
"""
Script para executar o teste específico sem pytest.
"""
import asyncio
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def run_specific_test():
    """Executar o teste específico sem pytest."""
    try:
        # Importar as dependências necessárias
        from unittest.mock import AsyncMock, patch
        from resync.core.connection_pool_manager import (
            DatabaseConnectionPool,
            ConnectionPoolConfig,
        )

        # Definir a classe de teste
        class TestConnectionPoolMetrics:
            """Test connection pool metrics collection."""

            async def setup_monitored_pool(self):
                """Create a monitored connection pool."""
                config = ConnectionPoolConfig(
                    pool_name="metrics_test_pool",
                    min_size=2,
                    max_size=10,
                    connection_timeout=5,
                    health_check_interval=10,
                )

                with patch("resync.core.pools.db_pool.create_async_engine") as mock_create_engine:
                    mock_engine = AsyncMock()
                    mock_create_engine.return_value = mock_engine

                    pool = DatabaseConnectionPool(config, "postgresql://test:test@localhost:5432/test")
                    await pool.initialize()
                    return pool

            async def test_pool_statistics_accuracy(self):
                """Test accuracy of pool statistics."""
                pool = await self.setup_monitored_pool()

                try:
                    # Get initial stats
                    initial_stats = pool.stats
                    print(f"Initial stats - Active: {initial_stats.active_connections}, Idle: {initial_stats.idle_connections}, Total: {initial_stats.total_connections}")

                    # Acquire some connections
                    connections = []

                    async def acquire_connection(connection_id: int):
                        async with pool.get_connection() as engine:
                            connections.append(connection_id)
                            # Check stats during connection
                            stats = pool.get_stats()
                            print(f"During connection {connection_id} - Active: {stats.active_connections}")
                            await asyncio.sleep(0.01)

                    # Acquire multiple connections
                    tasks = [acquire_connection(i) for i in range(3)]
                    await asyncio.gather(*tasks)

                    # Check final stats
                    final_stats = pool.get_stats()
                    print(f"Final stats - Hits: {final_stats.pool_hits}, Active: {final_stats.active_connections}, Creations: {final_stats.connection_creations}")

                    # Assertions
                    assert final_stats.pool_hits >= 3, f"Expected at least 3 pool hits, got {final_stats.pool_hits}"
                    assert final_stats.active_connections == 0, f"Expected 0 active connections, got {final_stats.active_connections}"
                    assert final_stats.connection_creations >= 3, f"Expected at least 3 connection creations, got {final_stats.connection_creations}"

                    print("✅ Test passed!")
                    return True

                finally:
                    await pool.close()

        # Executar o teste
        test_instance = TestConnectionPoolMetrics()
        success = await test_instance.test_pool_statistics_accuracy()
        return success

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_specific_test())
    sys.exit(0 if success else 1)
