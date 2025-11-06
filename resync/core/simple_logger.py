"""
Simple Logger Module (Core)

This module provides simple logging functionality for the core modules.
Re-exports get_logger from utils.simple_logger for compatibility.
"""

from __future__ import annotations

from resync.utils.simple_logger import get_logger

__all__ = ['get_logger']
