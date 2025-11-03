"""Correlation ID context management.

This module provides simple functions to set and get a correlation ID
used for request tracing throughout the application.  It acts as a
compatibility layer for legacy imports of ``resync.core.context``
which previously provided these functions.  The actual implementation
now lives in ``resync.utils.simple_logger``.

Usage:

    from resync.core.context import set_correlation_id, get_correlation_id
"""

from resync.utils.simple_logger import set_correlation_id, get_correlation_id  # noqa: F401

__all__ = ["set_correlation_id", "get_correlation_id"]
