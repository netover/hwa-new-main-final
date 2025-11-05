"""
AsyncNeo4jKnowledgeGraph implementation.

This module defines a minimal asynchronous knowledge graph backed by
Neo4j. It mirrors the API surface of the in-memory ``AsyncKnowledgeGraph``
stub and can be selected via the ``KG_BACKEND`` environment variable.

The driver is lazily initialised on instantiation using connection
parameters from environment variables:

- ``NEO4J_URI`` (default ``neo4j://localhost:7687``)
- ``NEO4J_USER`` (default ``neo4j``)
- ``NEO4J_PASSWORD`` (default empty)
- ``NEO4J_DATABASE`` (default ``neo4j``)

The graph stores "Memory" nodes keyed by a unique ``id`` property. The
content associated with each memory is persisted in a ``content``
property. Additional methods provide deletion, context retrieval and
approval tracking. When Neo4j support is unavailable, importing this
module will raise ``ImportError``.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

try:
    from neo4j import AsyncGraphDatabase  # type: ignore[attr-defined]
except Exception:
    # Expose a clear error when attempting to use this implementation
    AsyncGraphDatabase = None  # type: ignore


class AsyncNeo4jKnowledgeGraph:
    """Asynchronous knowledge graph backed by Neo4j.

    Provides a minimal API compatible with ``AsyncKnowledgeGraph``.
    A single driver instance is created on initialisation and reused
    for all operations. Call :meth:`close` when finished to close the
    underlying driver.
    """

    def __init__(self) -> None:
        if AsyncGraphDatabase is None:
            raise ImportError(
                "neo4j driver is not installed; cannot use AsyncNeo4jKnowledgeGraph"
            )
        uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        # Establish driver with basic authentication
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        self._database = os.getenv("NEO4J_DATABASE", "neo4j")

    async def close(self) -> None:
        """Close the underlying Neo4j driver."""
        if self._driver is not None:
            await self._driver.close()

    async def add_memory(self, memory_id: str, content: Any) -> None:
        """Persist a memory as a node labelled ``Memory``.

        If a memory node with the given ``memory_id`` already exists,
        its ``content`` property is updated.
        """
        # Record latency of Neo4j write operations when metrics are available
        from resync.core.monitoring.metrics import runtime_metrics  # type: ignore[attr-defined]
        import time
        start = time.perf_counter()
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                lambda tx, mid=memory_id, cnt=content: tx.run(
                    "MERGE (m:Memory {id: $id}) SET m.content = $content",
                    id=mid,
                    content=cnt,
                )
            )
        duration = time.perf_counter() - start
        try:
            runtime_metrics.neo4j_query_latency_seconds.observe(duration)
        except Exception:
            pass

    async def get_memory(self, memory_id: str) -> Optional[Any]:
        """Retrieve a memory's content by id.

        Returns ``None`` when the memory does not exist.
        """
        from resync.core.monitoring.metrics import runtime_metrics  # type: ignore[attr-defined]
        import time
        start = time.perf_counter()
        async with self._driver.session(database=self._database) as session:
            result = await session.execute_read(
                lambda tx, mid=memory_id: tx.run(
                    "MATCH (m:Memory {id: $id}) RETURN m.content AS content",
                    id=mid,
                )
            )
            record = await result.single()
        duration = time.perf_counter() - start
        try:
            runtime_metrics.neo4j_query_latency_seconds.observe(duration)
        except Exception:
            pass
        return record["content"] if record else None

    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory node by id."""
        from resync.core.monitoring.metrics import runtime_metrics  # type: ignore[attr-defined]
        import time
        start = time.perf_counter()
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                lambda tx, mid=memory_id: tx.run(
                    "MATCH (m:Memory {id: $id}) DETACH DELETE m",
                    id=mid,
                )
            )
        duration = time.perf_counter() - start
        try:
            runtime_metrics.neo4j_query_latency_seconds.observe(duration)
        except Exception:
            pass

    async def get_relevant_context(self, query: str, limit: int = 5) -> List[Any]:
        """Return a list of memory contents.

        This naive implementation ignores the query and returns up to
        ``limit`` arbitrary memories. A real implementation would
        perform semantic search or graph traversal based on the query.
        """
        from resync.core.monitoring.metrics import runtime_metrics  # type: ignore[attr-defined]
        import time
        start = time.perf_counter()
        async with self._driver.session(database=self._database) as session:
            result = await session.execute_read(
                lambda tx, lim=limit: tx.run(
                    "MATCH (m:Memory) RETURN m.content AS content LIMIT $limit",
                    limit=lim,
                )
            )
            records = [record["content"] for record in result]
        duration = time.perf_counter() - start
        try:
            runtime_metrics.neo4j_query_latency_seconds.observe(duration)
        except Exception:
            pass
        return records

    async def mark_memory_as_reviewed(self, memory_id: str, approved: bool) -> None:
        """Mark a memory node as reviewed and optionally approved."""
        from resync.core.monitoring.metrics import runtime_metrics  # type: ignore[attr-defined]
        import time
        start = time.perf_counter()
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                lambda tx, mid=memory_id, appr=approved: tx.run(
                    "MATCH (m:Memory {id: $id}) "
                    "SET m.reviewed = true, m.approved = $approved",
                    id=mid,
                    approved=appr,
                )
            )
        duration = time.perf_counter() - start
        try:
            runtime_metrics.neo4j_query_latency_seconds.observe(duration)
        except Exception:
            pass

__all__ = ["AsyncNeo4jKnowledgeGraph"]