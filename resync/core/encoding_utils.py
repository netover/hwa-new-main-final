"""Helpers for working with terminal encodings in log output."""

from __future__ import annotations

from typing import Optional, TextIO

DEFAULT_SUCCESS = "✅"
DEFAULT_ERROR = "❌"
FALLBACK_SUCCESS = "[OK]"
FALLBACK_ERROR = "[ERR]"
ENCODING_ERROR = "[ENCODING ERROR]"


def _resolve_encoding(stream: Optional[TextIO], encoding: Optional[str]) -> str:
    if encoding:
        return encoding
    if stream is not None and getattr(stream, "encoding", None):
        return stream.encoding  # type: ignore[attr-defined]
    return "utf-8"


def can_encode(text: str, *, encoding: Optional[str] = None, stream: Optional[TextIO] = None) -> bool:
    """Return True if the provided text can be encoded using the supplied encoding."""
    codec = _resolve_encoding(stream, encoding)
    try:
        text.encode(codec)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def symbol(
    success: bool,
    *,
    stream: Optional[TextIO] = None,
    encoding: Optional[str] = None,
) -> str:
    """Return a success/failure marker compatible with the target encoding."""
    marker = DEFAULT_SUCCESS if success else DEFAULT_ERROR
    if can_encode(marker, encoding=encoding, stream=stream):
        return marker

    fallback = FALLBACK_SUCCESS if success else FALLBACK_ERROR
    if can_encode(fallback, encoding=encoding, stream=stream):
        return fallback

    return ENCODING_ERROR


__all__ = ["can_encode", "symbol", "DEFAULT_SUCCESS", "DEFAULT_ERROR"]
