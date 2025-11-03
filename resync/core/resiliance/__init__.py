"""Alias package for resilience.

This directory exists to preserve imports of ``resync.core.resiliance``
which previously contained the circuit breaker implementation.  The
actual code now resides in ``resync.core.resilience``.  Importing
anything from this package will delegate to the corresponding module
within ``resync.core.resilience``.
"""

from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    # Delegate attribute access to the corrected package
    return getattr(import_module("resync.core.resilience"), name)


__all__ = []  # The underlying module defines its own public API
