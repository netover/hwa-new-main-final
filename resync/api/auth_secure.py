"""Deprecated authentication module (secure).

This module previously contained an independent implementation of
authentication and authorization endpoints. To reduce duplication and
centralize the authentication logic, the contents of this file have been
merged into ``resync.api.auth``.  All names defined in the
``auth`` module are re-exported here to maintain backwards compatibility
with code that still imports from ``resync.api.auth_secure``.

Importing this module will emit a deprecation warning and forward all
attributes from the canonical ``resync.api.auth`` module.
"""

from __future__ import annotations

import warnings

from resync.api.auth import *  # noqa: F401,F403

# Emit deprecation warning once when this module is imported.
warnings.warn(
    (
        "resync.api.auth_secure is deprecated. Please import from "
        "resync.api.auth instead. The secure authentication implementation "
        "has been consolidated into a single module."
    ),
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    name
    for name in globals().keys()
    if not name.startswith("_")
]



