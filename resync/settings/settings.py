"""Public settings API for the application.

This module re-exports the canonical settings from the legacy
`resync.config.settings` location to the new `resync.settings` namespace.
All application code should import from `resync.settings.settings`.
"""

from __future__ import annotations

# Re-export symbols to the new namespace to minimize churn
from resync.app_config.settings import (  # noqa: F401
    Settings,
    get_settings,
    clear_settings_cache,
    settings,
    load_settings,
)

__all__ = [
    "Settings",
    "get_settings",
    "clear_settings_cache",
    "settings",
    "load_settings",
]

