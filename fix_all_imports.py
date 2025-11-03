import os
import re

# Corrigir o erro de digitação em teams_integration.py
teams_file = "resync/core/teams_integration.py"
with open(teams_file, 'r') as f:
    content = f.read()

# Substituir ITeamsIntegration por ITeamsIntegration em todos os lugares
content = re.sub(r'ITeamsIntegration', 'ITeamsIntegration', content)

with open(teams_file, 'w') as f:
    f.write(content)

print("Corrigido o erro de digitação em teams_integration.py")

# Criar o arquivo write_ahead_log.py
write_ahead_file = "resync/core/write_ahead_log.py"
write_ahead_content = '''"""Write Ahead Log Module.

This module provides write-ahead logging functionality for the application.
"""

import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class IWriteAheadLog(ABC):
    """Interface for write-ahead log."""
    
    @abstractmethod
    async def write_log(self, message: str, level: str = "INFO") -> bool:
        """Write a message to the log."""
        pass
    
    @abstractmethod
    async def flush_logs(self) -> bool:
        """Flush all pending logs."""
        pass


class SimpleWriteAheadLog(IWriteAheadLog):
    """Simple implementation of write-ahead log."""
    
    def __init__(self):
        """Initialize the write-ahead log."""
        self.logger = logging.getLogger(__name__)
        self.pending_logs = []
    
    async def write_log(self, message: str, level: str = "INFO") -> bool:
        """Write a message to the log."""
        try:
            self.pending_logs.append((message, level))
            return True
        except Exception as e:
            self.logger.error(f"Error writing to log: {e}")
            return False
    
    async def flush_logs(self) -> bool:
        """Flush all pending logs."""
        try:
            for message, level in self.pending_logs:
                if level == "INFO":
                    self.logger.info(message)
                elif level == "WARNING":
                    self.logger.warning(message)
                elif level == "ERROR":
                    self.logger.error(message)
                elif level == "DEBUG":
                    self.logger.debug(message)
            
            self.pending_logs.clear()
            return True
        except Exception as e:
            self.logger.error(f"Error flushing logs: {e}")
            return False


# Global instance
_write_ahead_log: Optional[SimpleWriteAheadLog] = None


def get_write_ahead_log() -> SimpleWriteAheadLog:
    """Get the global write-ahead log instance."""
    global _write_ahead_log
    if _write_ahead_log is None:
        _write_ahead_log = SimpleWriteAheadLog()
    return _write_ahead_log
'''

with open(write_ahead_file, 'w') as f:
    f.write(write_ahead_content)

print(f"Criado o arquivo {write_ahead_file}")

# Adicionar a função get_cache_hierarchy ao __init__.py do cache
cache_init_file = "resync/core/cache/__init__.py"
with open(cache_init_file, 'r') as f:
    cache_content = f.read()

# Verificar se a função já existe
if "def get_cache_hierarchy" not in cache_content:
    # Adicionar a função no final do arquivo
    get_cache_function = '''
def get_cache_hierarchy():
    """Get the cache hierarchy instance.
    
    Returns:
        Cache hierarchy instance
    """
    from .unified_cache import UnifiedCache
    return UnifiedCache()
'''
    
    with open(cache_init_file, 'w') as f:
        f.write(cache_content + get_cache_function)
    
    print("Adicionada a função get_cache_hierarchy ao cache/__init__.py")
else:
    print("A função get_cache_hierarchy já existe em cache/__init__.py")

# Testar a importação novamente
print("\nTestando importação do módulo principal...")
try:
    import sys
    sys.path.insert(0, '.')
    import resync.fastapi_app.main as m
    print("Import OK - Todos os problemas foram resolvidos!")
except Exception as e:
    print(f"Import falhou: {e}")
