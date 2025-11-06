"""
Async Cache Module

This module provides async cache functionality.
Re-exports AsyncTTLCache for compatibility.
"""

from __future__ import annotations

from .cache.async_cache_refactored import AsyncTTLCache

__all__ = ['AsyncTTLCache']
