"""
Token-aware text chunking utility for RAG systems.

Splits text into overlapping chunks based on token count, respecting sentence boundaries.
Uses tiktoken if available; falls back to heuristic-based splitting.
"""

from __future__ import annotations

import re
from typing import Iterable
from typing import Iterator

# Optional import
try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False
    _ENC = None


def _tokens_len(s: str) -> int:
    """Estimate token count for a string."""
    if _HAS_TIKTOKEN and _ENC:
        return len(_ENC.encode(s))
    return max(1, len(s) // 4)  # rough approximation


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences based on punctuation."""
    text = re.sub(r"\s+", " ", text).strip()
    return re.split(r"(?<=[.!?])\s+", text) if text else []


def chunk_text(
    text: str, max_tokens: int = 512, overlap_tokens: int = 64
) -> Iterator[str]:
    """
    Chunk text in a token-aware way, respecting sentence boundaries and applying overlap.
    """
    if not text:
        return iter(())

    if _HAS_TIKTOKEN and _ENC:
        tokens = _ENC.encode(text)
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk = _ENC.decode(tokens[start:end])
            yield chunk
            start = max(0, end - overlap_tokens)
        return

    # Fallback: sentence-based chunking
    sents = _split_sentences(text)
    buf: list[str] = []
    cur = 0
    for s in sents:
        t = _tokens_len(s)
        if cur + t > max_tokens and buf:
            yield " ".join(buf)
            # Preserve last sentence as overlap
            last = buf[-1]
            buf = [last]
            cur = _tokens_len(last)
        buf.append(s)
        cur += t
    if buf:
        yield " ".join(buf)