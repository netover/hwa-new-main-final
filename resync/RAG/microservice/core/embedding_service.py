"""
Embedding service for generating vector embeddings using OpenAI or deterministic fallback.

Supports batch embedding with fallback to SHA-256 hash-based vectors for development.
"""

import hashlib
import os
from typing import List

from .config import CFG
from .interfaces import Embedder

# Optional imports
# OpenAI (production)
try:
    from openai import OpenAI  # openai>=1.x

    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


class EmbeddingService(Embedder):
    """
    Service for generating text embeddings using OpenAI or deterministic fallback.
    """

    def __init__(self) -> None:
        """
        Initialize the embedding service.

        Uses OpenAI if API key is set; otherwise, uses deterministic hash-based fallback.
        """
        self._use_openai = _HAS_OPENAI and bool(os.getenv("OPENAI_API_KEY"))
        self._client = (
            OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if self._use_openai else None
        )

    async def embed(self, text: str) -> List[float]:
        """
        Embed a single text string into a vector.

        Args:
            text: Input text to embed.

        Returns:
            List[float]: Embedding vector.
        """
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of text strings into vectors.

        Uses OpenAI if available; otherwise, uses deterministic hash-based fallback.

        Args:
            texts: List of input texts to embed.

        Returns:
            List[List[float]]: List of embedding vectors.
        """
        if self._use_openai:
            resp = self._client.embeddings.create(model=CFG.embed_model, input=texts)  # type: ignore[union-attr]
            return [d.embedding for d in resp.data]  # type: ignore[attr-defined]
        # Fallback determinístico para dev/CI (não semântico, mas estável)
        return [self._hash_vec(t) for t in texts]

    def _hash_vec(self, text: str) -> List[float]:
        """
        Generate a deterministic embedding vector from text using SHA-256 hash.

        This is a fallback for development/CI environments where OpenAI is not available.
        The hash is spread across the embedding dimension.

        Args:
            text: Input text to hash.

        Returns:
            List[float]: Deterministic embedding vector.
        """
        dim = CFG.embed_dim
        buf = [0.0] * dim
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # espalha 32 bytes ao longo do vetor
        for i, b in enumerate(h):
            buf[(i * 64) % dim] = b / 255.0
        return buf