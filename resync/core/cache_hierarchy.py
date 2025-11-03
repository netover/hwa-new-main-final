"""Cache Hierarchy Module.

This module provides cache hierarchy functionality for the application.
"""

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class ICacheHierarchy(ABC):
    """Interface for cache hierarchy."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache."""
        pass


class SimpleCacheHierarchy(ICacheHierarchy):
    """Simple implementation of cache hierarchy."""
    
    def __init__(self):
        """Initialize cache hierarchy."""
        self._cache: Dict[str, Any] = {}
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        return self._cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        self._cache[key] = value
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()


# Global instance
_cache_hierarchy: Optional[ICacheHierarchy] = None


def get_cache_hierarchy() -> ICacheHierarchy:
    """Get the global cache hierarchy instance."""
    global _cache_hierarchy
    if _cache_hierarchy is None:
        _cache_hierarchy = SimpleCacheHierarchy()
    return _cache_hierarchy
