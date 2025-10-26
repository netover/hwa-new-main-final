"""
Unit tests for IngestService.
"""

import hashlib
from unittest.mock import AsyncMock

import pytest

from resync.RAG.microservice.core.ingest import IngestService
from resync.RAG.microservice.core.interfaces import Embedder, VectorStore
from resync.RAG.microservice.core.config import CFG


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock(spec=Embedder)
    embedder.embed_batch.side_effect = lambda texts: [[0.1] * CFG.embed_dim for _ in texts]
    return embedder


@pytest.fixture
def mock_vector_store():
    store = AsyncMock(spec=VectorStore)
    store.exists_by_sha256.side_effect = lambda sha, collection: False  # Simulate no dedup
    store.upsert_batch = AsyncMock()
    store.count = AsyncMock(return_value=0)
    return store


@pytest.fixture
def ingest_service(mock_embedder, mock_vector_store):
    return IngestService(mock_embedder, mock_vector_store, batch_size=2)


@pytest.mark.asyncio
async def test_ingest_no_chunks(ingest_service):
    result = await ingest_service.ingest_document(
        tenant="test",
        doc_id="doc1",
        source="test",
        text="",
        ts_iso="2025-10-18T00:00:00Z",
    )
    assert result == 0


@pytest.mark.asyncio
async def test_ingest_with_chunks(ingest_service, mock_embedder, mock_vector_store):
    text = "This is a test document. It has multiple sentences. And more content."
    result = await ingest_service.ingest_document(
        tenant="test",
        doc_id="doc1",
        source="test",
        text=text,
        ts_iso="2025-10-18T00:00:00Z",
    )

    assert result == 3  # 3 chunks expected
    assert mock_embedder.embed_batch.call_count == 2  # 2 batches of 2, 1 of 1
    assert mock_vector_store.upsert_batch.call_count == 2


@pytest.mark.asyncio
async def test_ingest_with_deduplication(ingest_service, mock_embedder, mock_vector_store):
    # Simulate one chunk already exists
    def mock_exists(sha, collection):
        # First chunk (hash of "This is a test") is duplicate
        if sha == hashlib.sha256("This is a test".encode("utf-8")).hexdigest():
            return True
        return False

    mock_vector_store.exists_by_sha256.side_effect = mock_exists

    text = "This is a test. This is a test document."
    result = await ingest_service.ingest_document(
        tenant="test",
        doc_id="doc1",
        source="test",
        text=text,
        ts_iso="2025-10-18T00:00:00Z",
    )

    assert result == 1  # Only one new chunk
    assert mock_vector_store.upsert_batch.call_count == 1


@pytest.mark.asyncio
async def test_ingest_metrics_called(ingest_service, mock_embedder, mock_vector_store):
    text = "Test document."
    await ingest_service.ingest_document(
        tenant="test",
        doc_id="doc1",
        source="test",
        text=text,
        ts_iso="2025-10-18T00:00:00Z",
    )

    # Verify metrics were incremented
    assert ingest_service.store.upsert_seconds.time.called
    assert ingest_service.store.embed_seconds.time.called