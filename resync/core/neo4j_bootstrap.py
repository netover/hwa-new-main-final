"""
Neo4j index and constraint bootstrapper.

This module provides an asynchronous helper to ensure that required
indexes and constraints exist in the Neo4j database.  It is intended
to be invoked at application startup from the FastAPI lifespan when
the knowledge graph backend is configured to use Neo4j.  The helper
runs Cypher commands idempotently using ``CREATE CONSTRAINT ... IF NOT
EXISTS`` and ``CREATE INDEX ... IF NOT EXISTS``.  If the underlying
driver is unavailable the function does nothing.

Environment variables used:

- ``NEO4J_URI``: URI of the Neo4j instance (default
  ``neo4j://localhost:7687``)
- ``NEO4J_USER``: Username for authentication (default ``neo4j``)
- ``NEO4J_PASSWORD``: Password for authentication (default
  empty)
- ``NEO4J_DATABASE``: Database name (default ``neo4j``)

The list of Cypher statements executed here should remain in sync
with the contents of ``infra/neo4j_indexes.cypher``.
"""

from __future__ import annotations

import os
from typing import Sequence

try:
    from neo4j import AsyncGraphDatabase  # type: ignore
except Exception:
    # If the driver is not installed, expose a no‑op function
    AsyncGraphDatabase = None  # type: ignore


async def ensure_indexes(statements: Sequence[str] | None = None) -> None:
    """Ensure that required indexes and constraints exist in Neo4j.

    Connects to the Neo4j database using credentials from environment
    variables and executes a series of Cypher statements.  Each
    statement should include ``IF NOT EXISTS`` to avoid errors on
    re‑execution.  When the Neo4j driver is unavailable this function
    performs no action.

    Args:
        statements: Optional sequence of Cypher commands to run.  When
            omitted a default set of commands is used.
    """
    if AsyncGraphDatabase is None:
        # Driver is missing; nothing to do
        return
    # Determine connection parameters from environment with defaults
    uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    # Default statements correspond to the constraints and indexes
    # required by the Resync knowledge graph.  These should be kept in
    # sync with ``infra/neo4j_indexes.cypher``.  Additional indexes can
    # be appended by passing a custom ``statements`` sequence.
    default_statements = [
        "CREATE CONSTRAINT job_id_unique IF NOT EXISTS FOR (j:Job) REQUIRE j.id IS UNIQUE",
        "CREATE INDEX job_timestamp_index IF NOT EXISTS FOR (j:Job) ON (j.timestamp)",
        # Example of a compound index; uncomment if needed
        # "CREATE INDEX job_id_ts_index IF NOT EXISTS FOR (j:Job) ON (j.id, j.timestamp)",
    ]

    stmts = list(statements) if statements is not None else default_statements

    # Connect to Neo4j and execute the statements
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    async with driver:
        async with driver.session(database=database) as session:
            for stmt in stmts:
                await session.execute_write(lambda tx, s=stmt: tx.run(s))