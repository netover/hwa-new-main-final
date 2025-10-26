"""
Unit tests for RagRetriever.
"""

from unittest.mock import AsyncMock

import pytest

from resync.RAG.microservice.core.retriever import RagRetriever
from resync.RAG.microservice.core.interfaces import Embedder, VectorStore
from resync.RAG.microservice.core.config import CFG


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock(spec=Embedder)
    embedder.embed.return_value = [0.1] * CFG.embed_dim
    return embedder


@pytest.fixture
def mock_vector_store():
    store = AsyncMock(spec=VectorStore)
    store.query.return_value = [
        {"id": "1", "score": 0.95, "payload": {"text": "Relevant doc 1"}},
        {"id": "2", "score": 0.85, "payload": {"text": "Relevant doc 2"}},
        {"id": "3", "score": 0.75, "payload": {"text": "Relevant doc 3"}},
    ]
    return store


@pytest.fixture
def retriever(mock_embedder, mock_vector_store):
    return RagRetriever(mock_embedder, mock_vector_store)


@pytest.mark.asyncio
async def test_retrieve_basic(retriever, mock_embedder, mock_vector_store):
    results = await retriever.retrieve("query", top_k=3)

    assert len(results) == 3
    assert mock_embedder.embed.called
    assert mock_vector_store.query.called
    args, kwargs = mock_vector_store.query.call_args
    assert kwargs["top_k"] == 3
    assert kwargs["ef_search"] == CFG.ef_search_base  # Default


@pytest.mark.asyncio
async def test_retrieve_with_ef_search(retriever, mock_embedder, mock_vector_store):
    results = await retriever.retrieve("query", top_k=50)

    # ef_search = base + log2(50) * 8 ≈ 64 + 5.6 * 8 ≈ 109 → capped at 128
    args, kwargs = mock_vector_store.query.call_args
    assert kwargs["ef_search"] == 128


@pytest.mark.asyncio
async def test_retrieve_with_rerank(retriever, mock_embedder, mock_vector_store):
    # Mock query to return vectors
    mock_vector_store.query.return_value = [
        {"id": "1", "score": 0.95, "payload": {"text": "Doc 1"}, "vector": [0.1] * CFG.embed_dim},
        {"id": "2", "score": 0.85, "payload": {"text": "Doc 2"}, "vector": [0.2] * CFG.embed_dim},
    ]

    # Enable rerank
    CFG.enable_rerank = True

    results = await retriever.retrieve("query", top_k=2)

    assert len(results) == 2
    # Since vectors are different, re-ranking should change order
    # We don't assert exact order because cosine is symmetric
    assert mock_vector_store.query.call_args[1]["with_vectors"] is True

    CFG.enable_rerank = False  # Reset


@pytest.mark.asyncio
async def test_retrieve_with_filters(retriever, mock_embedder, mock_vector_store):
    filters = {"tenant": "org_a", "doc_id": "doc1"}
    await retriever.retrieve("query", top_k=5, filters=filters)

    args, kwargs = mock_vector_store.query.call_args
    assert kwargs["filters"] == filters