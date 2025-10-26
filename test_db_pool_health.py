#!/usr/bin/env python3
"""
Script simples para testar health_check do DB pool sem problemas de sintaxe.
"""

import asyncio
import sys
import os

# Adicionar diretório raiz ao path para importações
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_db_pool_health():
    """Testar health_check do DB pool de forma isolada."""
    try:
        # Importar apenas o necessário
        from resync.core.pools.db_pool import DatabaseConnectionPool
        from resync.core.pools.base_pool import ConnectionPoolConfig
        
        # Criar configuração mínima
        cfg = ConnectionPoolConfig(
            pool_name="test",
            min_size=1,
            max_size=2,
            connection_timeout=1,
            max_lifetime=1800
        )
        
        # Criar pool em memória (sem persistência) - SQLite simples
        pool = DatabaseConnectionPool(cfg, "sqlite+aiosqlite:///:memory:")
        
        # Inicializar pool
        await pool.initialize()

        # Executar health check de forma isolada
        ok = await pool.health_check()

        # Fechar pool
        await pool.close()
        
        # Exibir resultado
        print(f"health_check: {'ok' if ok else 'ERROR'}")
        
        return ok
        
    except Exception as e:
        print(f"ERRO: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_db_pool_health())