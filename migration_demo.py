#!/usr/bin/env python3
"""
Demonstração da Migração Gradual - Projeto Resync
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resync.core.migration_managers import CacheMigrationManager


async def demo() -> None:
    print("🚀 DEMONSTRAÇÃO: Migração Gradual do Cache")
    print("=" * 50)

    cache_mgr = CacheMigrationManager()  # type: ignore[no-untyped-call]
    await cache_mgr.initialize()  # type: ignore[no-untyped-call]

    print("\n1. Modo LEGACY:")
    cache_mgr.use_new_cache = False
    await cache_mgr.set("test", "legacy_value")
    value = await cache_mgr.get("test")
    print(f"   ✅ Valor: {value}")

    print("\n2. Modo NOVO (com dual-write):")
    cache_mgr.use_new_cache = True
    await cache_mgr.set("test2", "new_value")
    value = await cache_mgr.get("test2")
    print(f"   ✅ Valor: {value}")

    print("\n3. Teste de FALLBACK:")
    # Simular falha no novo cache
    if cache_mgr.new_cache is not None:
        original_get = cache_mgr.new_cache.get

        async def failing_get(key: str) -> None:
            raise Exception("Cache failure")

        cache_mgr.new_cache.get = failing_get  # type: ignore[method-assign]
        # Deve fazer fallback
        await cache_mgr.set("fallback_test", "fallback_value")
        value = await cache_mgr.get("fallback_test")
        print(f"   ✅ Fallback: {value}")

        cache_mgr.new_cache.get = original_get  # type: ignore[method-assign]

    await cache_mgr.shutdown()  # type: ignore[no-untyped-call]
    print("\n✅ Migração demonstrada com sucesso!")


if __name__ == "__main__":
    asyncio.run(demo())
