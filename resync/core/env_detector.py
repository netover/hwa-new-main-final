"""Environment detection helpers."""

from __future__ import annotations

import os
from typing import Literal

EnvironmentName = Literal["production", "staging", "development", "testing"]

_CURRENT_ENV: EnvironmentName = "production"


def _read_environment() -> EnvironmentName:
    value = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "production"
    value = value.strip().lower()
    if value not in {"production", "staging", "development", "testing"}:
        return "production"
    return value  # type: ignore[return-value]


def __init__() -> None:
    global _CURRENT_ENV
    _CURRENT_ENV = _read_environment()


def get_environment() -> EnvironmentName:
    return _CURRENT_ENV


def is_testing() -> bool:
    return _CURRENT_ENV == "testing"


def is_development() -> bool:
    return _CURRENT_ENV == "development"


def is_production() -> bool:
    return _CURRENT_ENV == "production"


__init__()

__all__ = [
    "get_environment",
    "is_testing",
    "is_development",
    "is_production",
    "EnvironmentName",
]
