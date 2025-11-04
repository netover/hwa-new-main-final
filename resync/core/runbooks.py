"""Lightweight runbook registry used by FastAPI endpoints and tests."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

RunbookHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


class RunbookRegistry:
    """In-memory registry for incident response runbooks."""

    def __init__(self) -> None:
        self._runbooks: Dict[str, RunbookHandler] = {}

    def register_runbook(self, name: str, handler: RunbookHandler) -> None:
        """Register or replace a runbook handler."""
        if not name:
            raise ValueError("Runbook name cannot be empty")
        self._runbooks[name] = handler
        logger.debug("runbook_registered", extra={"runbook": name})

    def list_runbooks(self) -> List[str]:
        """Return a sorted list of registered runbooks."""
        return sorted(self._runbooks.keys())

    def execute_runbook(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute a registered runbook if available."""
        handler = self._runbooks.get(name)
        if handler is None:
            logger.debug("runbook_not_found", extra={"runbook": name})
            return None
        payload = context or {}
        try:
            return handler(payload)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("runbook_execution_failed", extra={"runbook": name})
            return {
                "runbook": name,
                "success": False,
                "error": "execution_failed",
            }


# Global registry instance
runbook_registry = RunbookRegistry()


def register_default_runbooks() -> None:
    """Register a minimal no-op runbook for smoke tests."""

    def noop_runbook(context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "runbook": "noop",
            "success": True,
            "context": context,
            "message": "No-op runbook executed successfully.",
        }

    runbook_registry.register_runbook("noop", noop_runbook)


# Ensure at least one runbook is available for tests
register_default_runbooks()


__all__ = ["RunbookRegistry", "runbook_registry", "register_default_runbooks"]
