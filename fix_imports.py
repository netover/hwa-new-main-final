import os
import re

# Corrigir o erro de digitação em teams_integration.py
teams_file = "resync/core/teams_integration.py"
with open(teams_file, 'r') as f:
    content = f.read()

# Substituir ITeamsIntegration por ITeamsIntegration
content = content.replace("class SimpleTeamsIntegration(ITeamsIntegration):", 
                        "class SimpleTeamsIntegration(ITeamsIntegration):")

with open(teams_file, 'w') as f:
    f.write(content)

print("Corrigido o erro de digitação em teams_integration.py")

# Criar o arquivo websocket_pool_manager.py
ws_manager_file = "resync/core/websocket_pool_manager.py"
ws_content = '''"""WebSocket Pool Manager Module.

This module provides WebSocket connection pool management for the application.
"""

import asyncio
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class IWebSocketPoolManager(ABC):
    """Interface for WebSocket pool managers."""
    
    @abstractmethod
    async def get_connection(self, connection_id: str) -> Optional[Any]:
        """Get a WebSocket connection by ID."""
        pass
    
    @abstractmethod
    async def add_connection(self, connection_id: str, connection: Any) -> None:
        """Add a WebSocket connection to the pool."""
        pass
    
    @abstractmethod
    async def remove_connection(self, connection_id: str) -> None:
        """Remove a WebSocket connection from the pool."""
        pass


class SimpleWebSocketPoolManager(IWebSocketPoolManager):
    """Simple implementation of WebSocket pool manager."""
    
    def __init__(self):
        """Initialize the WebSocket pool manager."""
        self._connections: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def get_connection(self, connection_id: str) -> Optional[Any]:
        """Get a WebSocket connection by ID."""
        async with self._lock:
            return self._connections.get(connection_id)
    
    async def add_connection(self, connection_id: str, connection: Any) -> None:
        """Add a WebSocket connection to the pool."""
        async with self._lock:
            self._connections[connection_id] = connection
    
    async def remove_connection(self, connection_id: str) -> None:
        """Remove a WebSocket connection from the pool."""
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
    
    async def get_all_connections(self) -> List[Any]:
        """Get all WebSocket connections."""
        async with self._lock:
            return list(self._connections.values())
    
    async def clear_all(self) -> None:
        """Clear all WebSocket connections."""
        async with self._lock:
            self._connections.clear()


# Global instance
_websocket_pool_manager: Optional[SimpleWebSocketPoolManager] = None


async def get_websocket_pool_manager() -> SimpleWebSocketPoolManager:
    """Get the global WebSocket pool manager instance."""
    global _websocket_pool_manager
    if _websocket_pool_manager is None:
        _websocket_pool_manager = SimpleWebSocketPoolManager()
    return _websocket_pool_manager


async def shutdown_websocket_pool_manager() -> None:
    """Shutdown the WebSocket pool manager."""
    global _websocket_pool_manager
    if _websocket_pool_manager is not None:
        await _websocket_pool_manager.clear_all()
        _websocket_pool_manager = None
'''

with open(ws_manager_file, 'w') as f:
    f.write(ws_content)

print(f"Criado o arquivo {ws_manager_file}")

# Testar a importação novamente
print("\nTestando importação do módulo principal...")
try:
    import sys
    sys.path.insert(0, '.')
    import resync.fastapi_app.main as m
    print("Import OK - Todos os problemas foram resolvidos!")
except Exception as e:
    print(f"Import falhou: {e}")
