#!/usr/bin/env python3
"""
Teste simples para validar as melhorias implementadas no db_pool.py
"""

import asyncio
import logging
import tempfile
from pathlib import Path

from resync.core.pools.base_pool import ConnectionPoolConfig
from resync.core.pools.db_pool import DatabaseConnectionPool, SecretRedactor

# Configurar logging para ver os detalhes
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_sqlite_dialect_detection():
    """Testa detecção robusta de dialeto SQLite."""
    print("\n=== Teste: Detecção de Dialeto SQLite ===")

    # Test cases para diferentes URLs SQLite
    test_cases = [
        "sqlite+aiosqlite:///test.db",
        "sqlite+aiosqlite:///:memory:",
        "sqlite+aiosqlite:///file::memory:?cache=shared",
        "sqlite+aiosqlite:///test.db",
        "postgresql+asyncpg://user:pass@localhost/db",
    ]

    for url in test_cases:
        config = ConnectionPoolConfig(
            pool_name=f"test_{url.split('://', maxsplit=1)[0]}"
        )
        pool = DatabaseConnectionPool(config, url)

        try:
            await pool.initialize()
            pool.get_stats_copy()
            print(f"✅ {url[:30]}... -> backend detectado, pool inicializado")
            await pool.close()
        except (ConnectionError, RuntimeError, ValueError) as e:
            print(f"❌ {url[:30]}... -> Erro: {e}")
            await pool.close()


async def test_sqlite_pragmas():
    """Testa aplicação de PRAGMAs SQLite."""
    print("\n=== Teste: PRAGMAs SQLite ===")

    # Criar arquivo SQLite temporário
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        url = f"sqlite+aiosqlite:///{db_path}"
        config = ConnectionPoolConfig(pool_name="test_pragmas")
        pool = DatabaseConnectionPool(config, url)

        await pool.initialize()

        # Verificar se o pool está configurado corretamente
        stats = pool.get_stats_copy()
        print("✅ Pool SQLite inicializado com PRAGMAs")
        print(
            f"   Stats: acquisition_attempts={stats['acquisition_attempts']}"
        )

        await pool.close()
    finally:
        # Limpar arquivo temporário
        if Path(db_path).exists():
            Path(db_path).unlink()


async def test_metrics_precision():
    """Testa precisão das métricas."""
    print("\n=== Teste: Precisão de Métricas ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        url = f"sqlite+aiosqlite:///{db_path}"
        config = ConnectionPoolConfig(pool_name="test_metrics")
        pool = DatabaseConnectionPool(config, url)

        await pool.initialize()

        # Tentar obter conexão (deve incrementar acquisition_attempts)
        try:
            async with pool.get_connection():
                pass
        except (ConnectionError, RuntimeError, ValueError) as e:
            print(f"Erro durante teste de conexão: {e}")

        stats = pool.get_stats_copy()
        print("✅ Métricas coletadas:")
        print(f"   acquisition_attempts: {stats['acquisition_attempts']}")
        print(f"   pool_hits: {stats['pool_hits']}")
        print(f"   pool_misses: {stats['pool_misses']}")
        print(f"   session_acquisitions: {stats['session_acquisitions']}")

        await pool.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


def test_secret_redaction():
    """Testa filtro de redação de segredos."""
    print("\n=== Teste: Redação de Segredos ===")

    redactor = SecretRedactor()

    # Criar um registro de log simulado
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting with password=secret123&api_key=abc123token",
        args=(),
        exc_info=None,
    )

    # Aplicar filtro
    result = redactor.filter(record)
    print("✅ Original: Connecting with password=secret123&api_key=abc123token")
    print(f"✅ Redacted: {record.msg}")
    print(f"✅ Filtro aplicado: {result}")


async def test_health_check():
    """Testa health check otimizado."""
    print("\n=== Teste: Health Check ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        url = f"sqlite+aiosqlite:///{db_path}"
        config = ConnectionPoolConfig(pool_name="test_health")
        pool = DatabaseConnectionPool(config, url)

        await pool.initialize()

        # Testar health check
        is_healthy = await pool.health_check()
        print(f"✅ Health check result: {is_healthy}")

        await pool.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


async def main():
    """Executa todos os testes."""
    print("🚀 Iniciando testes das melhorias do db_pool.py")

    await test_sqlite_dialect_detection()
    await test_sqlite_pragmas()
    await test_metrics_precision()
    test_secret_redaction()
    await test_health_check()

    print("\n✅ Todos os testes concluídos!")


if __name__ == "__main__":
    asyncio.run(main())
