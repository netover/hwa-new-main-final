# Arquivo movido para resync/core/_deprecated/async_cache_refactored.py
# Devido a conflitos de namespace packages com mypy
# Todos os imports devem ser redirecionados

# Re-export para manter compatibilidade
from .._deprecated.async_cache_refactored import AsyncTTLCache

__all__ = ['AsyncTTLCache']
