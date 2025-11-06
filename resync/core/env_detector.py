"""Environment detection helpers."""

from __future__ import annotations

import os
from typing import Literal

EnvironmentName = Literal["production", "staging", "development", "testing"]

# Lazy initialization of current environment
_current_env: EnvironmentName | None = None


def _read_environment() -> EnvironmentName:
    value = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "production"
    value = value.strip().lower()
    if value not in {"production", "staging", "development", "testing"}:
        return "production"
    return value  # type: ignore[return-value]


def _ensure_initialized() -> None:
    global _current_env
    if _current_env is None:
        _current_env = _read_environment()


def get_environment() -> EnvironmentName:
    _ensure_initialized()
    assert _current_env is not None  # Should be initialized by _ensure_initialized
    return _current_env


def is_testing() -> bool:
    return get_environment() == "testing"


def is_development() -> bool:
    return get_environment() == "development"


def is_production() -> bool:
    return get_environment() == "production"


_ensure_initialized()

__all__ = [
    "get_environment",
    "is_testing",
    "is_development",
    "is_production",
    "EnvironmentName",
]
