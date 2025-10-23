"""
Protocols for RAG system components.

Defines interfaces for Embedder, VectorStore, and Retriever to enable dependency injection and testing.
"""

from __future__ import annotations

from typing import Any
from typing import Protocol


# pylint: disable=too-few-public-methods
class Embedder(Protocol):
    """
    Protocol for embedding text into vectors.
    """

    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


# pylint: disable=too-few-public-methods
class VectorStore(Protocol):
    """
    Protocol for storing and retrieving vector embeddings with metadata.
    """

    async def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
        collection: str | None = None,
    ) -> None: ...
    async def query(
        self,
        vector: list[float],
        top_k: int,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        ef_search: int | None = None,
        with_vectors: bool = False,
    ) -> list[dict[str, Any]]: ...
    async def count(self, collection: str | None = None) -> int: ...
    async def exists_by_sha256(
        self, sha256: str, collection: str | None = None
    ) -> bool: ...


# pylint: disable=too-few-public-methods
class Retriever(Protocol):
    """
    Protocol for retrieving relevant documents based on a query.
    """

    async def retrieve(
        self, query: str, top_k: int = 10, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...