from __future__ import annotations

import math
from typing import Any
from typing import List

from .config import CFG
from .interfaces import Embedder
from .interfaces import Retriever
from .interfaces import VectorStore
from .monitoring import query_seconds


class RagRetriever(Retriever):
    def __init__(self, embedder: Embedder, store: VectorStore):
        self.embedder = embedder
        self.store = store

    async def retrieve(
        self, query: str, top_k: int = 10, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        top_k = min(top_k, CFG.max_top_k)
        vec = await self.embedder.embed(query)
        ef = CFG.ef_search_base + int(math.log2(max(10, top_k)) * 8)
        ef = min(ef, CFG.ef_search_max)
        with query_seconds.time():
            hits = await self.store.query(
                vector=vec,
                top_k=top_k,
                collection=CFG.collection_read,
                filters=filters,
                ef_search=ef,
                with_vectors=False if not CFG.enable_rerank else True,
            )
        if not CFG.enable_rerank:
            return hits

        # Re-rank leve (cosine com vetor do Qdrant, caso retornado)
        if hits and "vector" in hits[0]:

            def cos(a: List[float], b: List[float]) -> float:
                import math

                da = math.sqrt(sum(x * x for x in a))
                db = math.sqrt(sum(x * x for x in b))
                if da == 0 or db == 0:
                    return 0.0
                return sum(x * y for x, y in zip(a, b)) / (da * db)

            q = vec
            hits.sort(key=lambda h: cos(q, h.get("vector") or []), reverse=True)
        return hits
