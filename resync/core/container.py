"""Dependency injection container shim.

Older parts of the codebase refer to ``resync.core.container`` for
retrieving the application's dependency injection container.  The
implementation has since moved to ``resync.core.di_container``.  This
module re‑exports the global container instance as ``app_container``
for backwards compatibility.
"""

from resync.core.di_container import container as app_container  # noqa: F401

__all__ = ["app_container"]
