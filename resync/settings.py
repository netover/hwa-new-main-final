"""Compatibility shim for settings.

This module re‑exports the application settings from the new location
(`resync.config.settings`).  Some parts of the codebase still import
`resync.settings` from the old path.  To maintain backward
compatibility and avoid `ImportError` exceptions, this module simply
imports the `settings` instance from the updated configuration module
and exposes it at the top level.

Example:

    from resync.settings import settings

"""

from resync.config.settings import settings  # noqa: F401

__all__ = ["settings"]
