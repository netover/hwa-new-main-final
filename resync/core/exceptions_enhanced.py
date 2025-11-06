"""Enhanced exceptions module.

Historically, the project defined a second, slightly modified copy of
``resync.utils.exceptions`` under the name ``resync.core.exceptions_enhanced``.
Maintaining multiple copies of the same exception hierarchy led to
confusion and import errors when modules referenced different versions.

This module now simply re-exports everything from the canonical
``resync.utils.exceptions``. Importing from this module continues to
work as before while ensuring that all parts of the codebase refer to
the same class definitions. New code should import exceptions from
``resync.utils.exceptions`` directly to avoid unnecessary indirection.
"""

from __future__ import annotations

from resync.utils.exceptions import *  # noqa: F401,F403

# __all__ is intentionally omitted for compatibility module



