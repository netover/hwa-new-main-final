"""Simplified asynchronous knowledge graph interface.

This module provides a bare-bones asynchronous interface to a knowledge
graph.  In the full application, the knowledge graph was backed by
Neo4j and stored conversational context, embeddings, and metadata.

To decouple the rest of the system from the Neo4j dependency and to
simplify testing, this implementation keeps data in memory and
implements only a small subset of the original API surface.  It can be
replaced with a real graph database implementation by adhering to the
same method signatures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import os

# Attempt to import the Neo4j-backed knowledge graph. When the Neo4j
# driver or implementation is unavailable this will fail and the
# in-memory stub will be used instead. The environment variable
# ``KG_BACKEND`` governs which implementation to instantiate via
# :func:`create_knowledge_graph`.
try:
    from .neo4j_knowledge_graph import AsyncNeo4jKnowledgeGraph  # type: ignore[attr-defined]
except Exception:
    AsyncNeo4jKnowledgeGraph = None  # type: ignore


class AsyncKnowledgeGraph:
    """In-memory knowledge graph stub.

    Stores memories (conversational messages or facts) keyed by a unique
    identifier.  All methods are asynchronous to mirror the original
    implementation.
    """

    def __init__(self) -> None:
        # Use a simple dictionary to store memories.  The key is a
        # user-provided memory_id and the value is arbitrary data.
        self._memories: Dict[str, Any] = {}

    async def add_memory(self, memory_id: str, content: Any) -> None:
        """Add a memory to the knowledge graph."""
        self._memories[memory_id] = content

    async def get_memory(self, memory_id: str) -> Optional[Any]:
        """Retrieve a memory by its id."""
        return self._memories.get(memory_id)

    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory from the knowledge graph."""
        if memory_id in self._memories:
            del self._memories[memory_id]

    async def get_relevant_context(self, query: str, limit: int = 5) -> List[Any]:
        """Return a list of memories relevant to the query.

        This stub simply returns up to ``limit`` arbitrary memories.  A
        real implementation would perform semantic search or graph
        traversal based on the query.
        """
        # Return the first ``limit`` values from the dictionary
        return list(self._memories.values())[:limit]

    async def mark_memory_as_reviewed(self, memory_id: str, approved: bool) -> None:
        """Mark a memory as reviewed.

        This stub does not track review status; it simply ensures the
        memory exists and ignores the approval flag.
        """
        # Ensure the memory exists; no other action taken
        _ = self._memories.get(memory_id)


# Factory function to create an appropriate knowledge graph backend.
def create_knowledge_graph() -> "AsyncKnowledgeGraph | AsyncNeo4jKnowledgeGraph":
    """Create a knowledge graph instance based on configuration.

    When ``KG_BACKEND`` is set to ``"neo4j"`` and the Neo4j driver is
    available, an instance of :class:`AsyncNeo4jKnowledgeGraph` is
    returned. Otherwise the default :class:`AsyncKnowledgeGraph` stub
    backed by in-memory storage is used.

    Returns:
        An asynchronous knowledge graph implementation.
    """
    backend = os.getenv("KG_BACKEND", "stub").lower()
    if backend == "neo4j" and AsyncNeo4jKnowledgeGraph is not None:
        try:
            return AsyncNeo4jKnowledgeGraph()  # type: ignore[return-value]
        except Exception:
            # Fall back to in-memory stub on any initialization error
            pass
    return AsyncKnowledgeGraph()  # type: ignore[return-value]


__all__ = ["AsyncKnowledgeGraph", "create_knowledge_graph"]



