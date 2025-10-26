"""
Idempotent document ingestion service for RAG systems.

Handles chunking, deduplication by SHA-256, batch embedding, and upsert to Qdrant.
Integrates Prometheus metrics for observability.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from .chunking import chunk_text
from .config import CFG
from .interfaces import Embedder
from .interfaces import VectorStore
from .monitoring import embed_seconds
from .monitoring import jobs_total
from .monitoring import upsert_seconds

logger = logging.getLogger(__name__)


class IngestService:
    """
    Ingestão idempotente:
    - chunking "token-aware"
    - dedup por sha256 do chunk normalizado
    - embed em lote com batch fixo
    - upsert no Qdrant com payload completo
    """

    def __init__(self, embedder: Embedder, store: VectorStore, batch_size: int = 128):
        self.embedder = embedder
        self.store = store
        self.batch_size = batch_size

    async def ingest_document(
        self,
        *,
        tenant: str,
        doc_id: str,
        source: str,
        text: str,
        ts_iso: str,
        tags: list[str] | None = None,
        graph_version: int = 1,
    ) -> int:
        chunks = list(chunk_text(text, max_tokens=512, overlap_tokens=64))
        if not chunks:
            return 0

        ids: list[str] = []
        payloads: list[dict[str, Any]] = []
        texts_for_embed: list[str] = []

        for i, ck in enumerate(chunks):
            ck_norm = ck.strip()
            sha = hashlib.sha256(ck_norm.encode("utf-8")).hexdigest()
            # dedup duro por sha256 (consulta por payload)
            exists = await self.store.exists_by_sha256(
                sha, collection=CFG.collection_read
            )
            if exists:
                continue
            chunk_id = f"{doc_id}#c{i:06d}"
            ids.append(chunk_id)
            payloads.append(
                {
                    "tenant": tenant,
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "source": source,
                    "section": None,
                    "ts": ts_iso,
                    "tags": tags or [],
                    "neighbors": [],
                    "graph_version": graph_version,
                    "sha256": sha,
                }
            )
            texts_for_embed.append(ck_norm)

        if not ids:
            logger.info("No new chunks to ingest (dedup hit) doc_id=%s", doc_id)
            return 0

        # embed em lotes
        total_upsert = 0
        t0 = time.perf_counter()
        for start in range(0, len(texts_for_embed), self.batch_size):
            batch_texts = texts_for_embed[start : start + self.batch_size]
            with embed_seconds.time():
                vecs = await self.embedder.embed_batch(batch_texts)
            with upsert_seconds.time():
                await self.store.upsert_batch(
                    ids=ids[start : start + self.batch_size],
                    vectors=vecs,
                    payloads=payloads[start : start + self.batch_size],
                    collection=CFG.collection_write,
                )
            total_upsert += len(batch_texts)

        jobs_total.labels(status="ingested").inc()
        logger.info(
            "Ingested %s chunks for doc_id=%s in %.2fs",
            total_upsert,
            doc_id,
            time.perf_counter() - t0,
        )
        return total_upsert