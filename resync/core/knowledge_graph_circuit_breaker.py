# resync/core/knowledge_graph_circuit_breaker.py
"""
Circuit Breaker wrapper for AsyncKnowledgeGraph.

This module provides a circuit breaker-protected interface to Neo4j operations,
preventing cascading failures when the Neo4j service becomes unavailable.
"""

from typing import Any

from resync.core.exceptions import KnowledgeGraphError
from resync.core.structured_logger import get_logger
from resync.core.health.circuit_breaker import CircuitBreaker
from resync.core.knowledge_graph import AsyncKnowledgeGraph

logger = get_logger(__name__)

# Circuit breaker for Neo4j operations
neo4j_circuit_breaker = CircuitBreaker(
    failure_threshold=5,  # Open after 5 failures
    recovery_timeout=120,  # Try to recover after 2 minutes
)


class CircuitBreakerAsyncKnowledgeGraph:
    """
    Circuit breaker-protected wrapper for AsyncKnowledgeGraph.

    This class wraps all Neo4j operations with circuit breaker protection,
    preventing cascading failures when Neo4j becomes unavailable.
    """

    def __init__(self):
        self._kg = AsyncKnowledgeGraph()

    @property
    def client(self) -> Any:
        """Gets the underlying Neo4j driver client."""
        return self._kg.client

    async def close(self):
        """Fecha a conexão com o driver do Neo4j."""
        await self._kg.close()

    async def add_content(self, content: str, metadata: dict[str, Any]) -> str:
        """Adds a piece of content with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(
                self._kg.add_content, content, metadata
            )
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning("neo4j_circuit_breaker_open", operation="add_content")
                raise KnowledgeGraphError(
                    "Neo4j service is temporarily unavailable due to circuit breaker protection."
                ) from e
            raise

    async def get_relevant_context(self, user_query: str, top_k: int = 10) -> str:
        """Retrieves relevant context with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(
                self._kg.get_relevant_context, user_query, top_k
            )
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning(
                    "neo4j_circuit_breaker_open", operation="get_relevant_context"
                )
                # Return empty context instead of failing
                logger.info("returning_empty_context_due_to_circuit_breaker")
                return ""
            raise

    async def add_conversation(
        self,
        user_query: str,
        agent_response: str,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Stores a conversation with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(
                self._kg.add_conversation, user_query, agent_response, agent_id, context
            )
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning(
                    "neo4j_circuit_breaker_open", operation="add_conversation"
                )
                raise KnowledgeGraphError(
                    "Neo4j service is temporarily unavailable due to circuit breaker protection."
                ) from e
            raise

    async def search_similar_issues(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Searches similar issues with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(
                self._kg.search_similar_issues, query, limit
            )
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning(
                    "neo4j_circuit_breaker_open", operation="search_similar_issues"
                )
                # Return empty list instead of failing
                logger.info("returning_empty_results_due_to_circuit_breaker")
                return []
            raise

    async def get_all_recent_conversations(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Gets recent conversations with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(
                self._kg.get_all_recent_conversations, limit
            )
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning(
                    "neo4j_circuit_breaker_open",
                    operation="get_all_recent_conversations",
                )
                # Return empty list instead of failing
                logger.info("returning_empty_results_due_to_circuit_breaker")
                return []
            raise

    async def get_memories(self, agent_id: str) -> list[dict[str, Any]]:
        """Gets memories for agent with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(self._kg.get_memories, agent_id)
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning("neo4j_circuit_breaker_open", operation="get_memories")
                # Return empty list instead of failing
                logger.info("returning_empty_results_due_to_circuit_breaker")
                return []
            raise

    async def get_all_memories(self) -> list[dict[str, Any]]:
        """Gets all memories with circuit breaker protection."""
        try:
            return await neo4j_circuit_breaker.call(self._kg.get_all_memories)
        except RuntimeError as e:
            if "Circuit breaker is open" in str(e):
                logger.warning(
                    "neo4j_circuit_breaker_open", operation="get_all_memories"
                )
                # Return empty list instead of failing
                logger.info("returning_empty_results_due_to_circuit_breaker")
                return []
            raise


def get_neo4j_circuit_breaker_stats():
    """Get circuit breaker statistics for monitoring."""
    return neo4j_circuit_breaker.get_stats()


# Factory function to create circuit breaker protected knowledge graph
def create_circuit_breaker_knowledge_graph() -> CircuitBreakerAsyncKnowledgeGraph:
    """Factory function to create a circuit breaker protected knowledge graph instance."""
    return CircuitBreakerAsyncKnowledgeGraph()
