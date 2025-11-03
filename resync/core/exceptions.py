"""Resync Core Exceptions (re-export).

This module simply re-exports the exception hierarchy defined in
``resync.utils.exceptions``. Historically the exception classes were
duplicated in both ``resync.core.exceptions`` and ``resync.utils.exceptions``.
Maintaining two divergent copies led to inconsistencies in class identity and
import cycles throughout the project. To simplify the codebase and ensure
there is a single source of truth for all exception definitions, the core
module now delegates entirely to the utils module.

Existing imports of ``resync.core.exceptions`` will continue to work
transparently, as all names are re-exported from ``resync.utils.exceptions``.
New code should import exceptions from ``resync.utils.exceptions`` directly
wherever possible.
"""

from __future__ import annotations

# Re-export everything from the utils exceptions module. The noqa comment
# suppresses the linter warning about wildcard imports, which are
# intentional here to preserve backwards compatibility without having to
# manually list every class and constant defined in the utils exceptions.
from resync.utils.exceptions import *  # noqa: F401,F403

__all__ = [
    name
    for name in globals().keys()
    if not name.startswith("_")
]



