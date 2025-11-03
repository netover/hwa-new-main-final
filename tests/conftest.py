"""Pytest configuration: provide safe mocks for optional dependencies during collection.

This prevents ModuleNotFoundError for optional libs when tests don't actually need them.
"""

import os
import sys
import types

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




