"""
Base Cache Module

This module provides the abstract base class for cache implementations in the resync application.
It defines the core cache operations that all cache implementations must support.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseCache(ABC):
    """
    Abstract base class for cache implementations.

    This class defines the core cache operations that all cache implementations
    must support. Concrete implementations should inherit from this class and
    provide specific storage mechanisms (e.g., in-memory, Redis, file-based).
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache by key.

        Args:
            key: The cache key to look up

        Returns:
            The cached value if found, None otherwise
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store a value in the cache with an optional time-to-live.

        Args:
            key: The cache key to store the value under
            value: The value to cache
            ttl: Optional time-to-live in seconds. If None, the value
                 will not expire unless the implementation has a default TTL

        Returns:
            True if the value was successfully stored, False otherwise
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Remove a value from the cache by key.

        Args:
            key: The cache key to remove

        Returns:
            True if the key was found and removed, False if the key was not found
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Remove all values from the cache.

        This operation should clear the entire cache, removing all keys and values.
        """
        pass
