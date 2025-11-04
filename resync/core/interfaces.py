"""Backward compatible interface aliases for legacy imports."""

from __future__ import annotations

from resync.utils.interfaces import (
    IAgentManager,
    IAuditQueue,
    IConnectionManager,
    IFileIngestor,
    IKnowledgeGraph,
    ITWSClient,
)

__all__ = [
    "IAgentManager",
    "IAuditQueue",
    "IConnectionManager",
    "IFileIngestor",
    "IKnowledgeGraph",
    "ITWSClient",
]
