"""
Prometheus metrics for RAG system observability.
"""

from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Histogram

embed_seconds = Histogram("rag_embed_seconds", "Latency for embedding batches")
upsert_seconds = Histogram("rag_upsert_seconds", "Latency for vector upserts")
query_seconds = Histogram("rag_query_seconds", "Latency for vector queries")

jobs_total = Counter("rag_jobs_total", "RAG jobs", ["status"])
collection_vectors = Gauge(
    "rag_collection_vectors", "Vectors in current read collection"
)