"""
Qdrant-based vector store implementation for RAG.

Provides async-safe upsert, query, and deduplication with payload indexing.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from .config import CFG
from .interfaces import VectorStore

logger = logging.getLogger(__name__)

# Optional imports - defer error until actual usage
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm
    QDRANT_AVAILABLE = True
except ImportError:
    QdrantClient = None
    qm = None
    QDRANT_AVAILABLE = False


def _to_thread(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))


class QdrantVectorStore(VectorStore):
    """
    Encapsula operações de upsert/query no Qdrant com criação automática da coleção,
    índices de payload e filtros. Todas as chamadas do client (bloqueantes) são
    executadas fora do event loop.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection: Optional[str] = None,
        dim: int = CFG.embed_dim,
    ):
        if not QDRANT_AVAILABLE:
            raise RuntimeError("qdrant-client is required. pip install qdrant-client")

        self._client = QdrantClient(
            url or CFG.qdrant_url, api_key=api_key or CFG.qdrant_api_key, timeout=60.0
        )
        self._collection_default = collection or CFG.collection_write
        self._dim = dim
        self._ensure_collection(self._collection_default)

    def _ensure_collection(self, collection: str) -> None:
        try:
            self._client.get_collection(collection)
            return
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        logger.info("Creating Qdrant collection: %s", collection)
        _to_thread(
            self._client.recreate_collection,
            collection_name=collection,
            vectors_config=qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE),
            optimizers_config=qm.OptimizersConfigDiff(default_segment_number=2),
            hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=256),
            shard_number=1,
        )
        # payload indexes (best-effort)
        for key, schema in [
            ("tenant", qm.PayloadSchemaType.KEYWORD),
            ("doc_id", qm.PayloadSchemaType.KEYWORD),
            ("tags", qm.PayloadSchemaType.KEYWORD),
            ("ts", qm.PayloadSchemaType.DATETIME),
            ("graph_version", qm.PayloadSchemaType.INTEGER),
            ("sha256", qm.PayloadSchemaType.KEYWORD),
        ]:
            try:
                self._client.create_payload_index(
                    collection, field_name=key, field_schema=schema
                )
            except Exception:  # pylint: disable=broad-exception-caught
                # índice já existe ou versão antiga; segue
                pass

    async def upsert_batch(
        self,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        collection: Optional[str] = None,
    ) -> None:
        col = collection or self._collection_default
        points = [
            qm.PointStruct(id=i, vector=v, payload=p)
            for i, v, p in zip(ids, vectors, payloads)
        ]
        await _to_thread(
            self._client.upsert, collection_name=col, points=points, wait=True
        )

    def _to_filter(self, filters: Optional[Dict[str, Any]]) -> Optional[qm.Filter]:
        if not filters:
            return None
        must = []
        for k, v in filters.items():
            if v is None:
                continue
            must.append(qm.FieldCondition(key=k, match=qm.MatchValue(value=v)))
        return qm.Filter(must=must) if must else None

    async def query(
        self,
        vector: List[float],
        top_k: int,
        collection: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        ef_search: Optional[int] = None,
        with_vectors: bool = False,
    ) -> List[Dict[str, Any]]:
        col = collection or CFG.collection_read
        qf = self._to_filter(filters)
        params = qm.SearchParams(
            hnsw_ef=min(
                max(CFG.ef_search_base, (ef_search or CFG.ef_search_base)),
                CFG.ef_search_max,
            )
        )
        res = await _to_thread(
            self._client.search,
            collection_name=col,
            query_vector=vector,
            limit=top_k,
            query_filter=qf,
            with_payload=True,
            with_vectors=with_vectors,
            search_params=params,
        )
        out: List[Dict[str, Any]] = []
        for r in res:
            item = {"id": str(r.id), "score": float(r.score), "payload": r.payload}
            if with_vectors and getattr(r, "vector", None) is not None:
                item["vector"] = r.vector  # type: ignore[attr-defined]
            out.append(item)
        return out

    async def count(self, collection: Optional[str] = None) -> int:
        col = collection or CFG.collection_read
        info = await _to_thread(self._client.get_collection, col)
        return int(info.vectors_count or 0)

    async def exists_by_sha256(
        self, sha256: str, collection: Optional[str] = None
    ) -> bool:
        col = collection or CFG.collection_read
        flt = qm.Filter(
            must=[qm.FieldCondition(key="sha256", match=qm.MatchValue(value=sha256))]
        )
        # scroll é mais barato do que search para checagem exata
        res, _ = await _to_thread(
            self._client.scroll,
            collection_name=col,
            scroll_filter=flt,
            limit=1,
            with_payload=False,
        )
        return bool(res)


def get_default_store() -> QdrantVectorStore:
    return QdrantVectorStore()