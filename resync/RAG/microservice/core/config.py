"""
Configuration for the Qdrant-only RAG system.

Defines environment variables and defaults for Qdrant connection, embedding model, and search parameters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(env: str, default: bool = False) -> bool:
    v = os.getenv(env)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RagConfig:
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY")
    collection_write: str = os.getenv("QDRANT_COLLECTION", "knowledge_v1")
    collection_read: str = os.getenv(
        "RAG_COLLECTION_READ", os.getenv("QDRANT_COLLECTION", "knowledge_v1")
    )
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    embed_dim: int = int(os.getenv("EMBED_DIM", "1536"))
    max_top_k: int = int(os.getenv("RAG_MAX_TOPK", "50"))
    ef_search_base: int = int(os.getenv("RAG_EF_SEARCH_BASE", "64"))
    ef_search_max: int = int(os.getenv("RAG_EF_SEARCH_MAX", "128"))
    max_neighbors: int = int(os.getenv("RAG_MAX_NEIGHBORS", "32"))
    enable_rerank: bool = _bool("RAG_RERANKER_ON", False)


CFG = RagConfig()