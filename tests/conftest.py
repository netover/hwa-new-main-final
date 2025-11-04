"""Pytest configuration: provide safe mocks for optional dependencies during collection.

This prevents ModuleNotFoundError for optional libs when tests don't actually need them.
"""

import asyncio
import os
import sys
import types

import pytest

# Desabilita integrações pesadas durante a coleta
os.environ.setdefault("RESYNC_DISABLE_REDIS", "1")
os.environ.setdefault("RESYNC_EAGER_BOOT", "0")

# Mocks mínimos para dependências opcionais apenas se não estiverem disponíveis
_OPTIONAL_DEPS = ["aiofiles", "uvloop", "websockets"]

for name in _OPTIONAL_DEPS:
    if name not in sys.modules:
        try:
            __import__(name)
        except ImportError:
            # Só cria mock se realmente não conseguir importar
            sys.modules[name] = types.SimpleNamespace()


@pytest.fixture
def event_loop():
    """Compat fixture for pytest-asyncio strict mode."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()




