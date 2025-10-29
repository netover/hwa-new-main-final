"""
Legacy API module - DEPRECATED

This module has been migrated to fastapi_app/api/v1.
Please use the new modular FastAPI structure instead.
"""

from __future__ import annotations

# This module is deprecated and will be removed in a future version
# All functionality has been migrated to fastapi_app/api/v1
import warnings

warnings.warn(
    "resync.api is deprecated. Use fastapi_app.api.v1 instead.",
    DeprecationWarning,
    stacklevel=2,
)
