"""Structured logging helper used across the legacy codebase."""

from __future__ import annotations

import logging
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _ensure_handler(logger: logging.Logger, fmt: str) -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)


def get_logger(name: Optional[str] = None, fmt: str = _DEFAULT_FORMAT) -> logging.Logger:
    """Return a logger configured with a default structured formatter."""
    logger = logging.getLogger(name)
    _ensure_handler(logger, fmt)
    logger.propagate = False
    return logger


__all__ = ["get_logger"]
