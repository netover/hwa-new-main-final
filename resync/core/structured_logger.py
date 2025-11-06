"""Structured logging utilities with encoding-aware safety helpers."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from .encoding_utils import (
    DEFAULT_ERROR,
    DEFAULT_SUCCESS,
    ENCODING_ERROR,
    FALLBACK_ERROR,
    FALLBACK_SUCCESS,
    can_encode,
    symbol,
)

DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class SafeEncodingFormatter(logging.Formatter):
    """Formatter that replaces unencodable characters with safe fallbacks."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, style: str = "%") -> None:  # type: ignore
        super().__init__(fmt or DEFAULT_FORMAT, datefmt=datefmt, style=style)

    def format(self, record: logging.LogRecord) -> str:
        stream = getattr(sys, "stdout", None)
        encoding = getattr(stream, "encoding", None)

        allowed_success = symbol(True, stream=stream, encoding=encoding)
        allowed_error = symbol(False, stream=stream, encoding=encoding)

        original_msg = record.getMessage()
        safe_message = (
            original_msg.replace(DEFAULT_SUCCESS, allowed_success)
            .replace(DEFAULT_ERROR, allowed_error)
            .replace(FALLBACK_SUCCESS, allowed_success)
            .replace(FALLBACK_ERROR, allowed_error)
        )

        if not can_encode(safe_message, encoding=encoding, stream=stream):
            safe_message = (
                safe_message.encode("ascii", "replace").decode("ascii")
                + f" {ENCODING_ERROR}"
            )

        original_msg_obj = record.msg
        original_args = record.args
        record.msg = safe_message
        record.args = ()
        try:
            formatted = super().format(record)
        finally:
            record.msg = original_msg_obj
            record.args = original_args
        return formatted


def get_logger(name: Optional[str] = None, fmt: str = DEFAULT_FORMAT) -> logging.Logger:
    """Return a logger configured with the safe formatter."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SafeEncodingFormatter(fmt=fmt))
        logger.addHandler(handler)
    logger.propagate = False
    return logger


__all__ = ["SafeEncodingFormatter", "get_logger"]
