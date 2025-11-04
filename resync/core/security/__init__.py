"""Security helpers for sanitising user input and IDs."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any, Dict, Tuple, Type, TypeVar, Union, cast

from resync.core import env_detector

try:  # pragma: no cover - optional import for runtime compatibility
    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import core_schema
except ImportError:  # pragma: no cover - fallback when Pydantic is not available
    GetCoreSchemaHandler = GetJsonSchemaHandler = None  # type: ignore[assignment]
    JsonSchemaValue = Dict[str, Any]  # type: ignore[misc,assignment]
    core_schema = None  # type: ignore[assignment]

T = TypeVar("T")


class SafeAgentID(str):
    """Simple type enforcing safe agent identifiers."""

    def __new__(cls, value: str) -> "SafeAgentID":
        if not value or not value.strip():
            raise ValueError("Agent ID cannot be empty")
        sanitized = value.strip()
        if any(ch.isspace() for ch in sanitized):
            raise ValueError("Agent ID cannot contain whitespace")
        return cast("SafeAgentID", str.__new__(cls, sanitized))

    # ------------------------------------------------------------------
    # Pydantic compatibility hooks (v1 & v2)
    # ------------------------------------------------------------------
    @classmethod
    def _validate(cls, value: Any) -> "SafeAgentID":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(value)
        raise TypeError("SafeAgentID requires a string value")

    @classmethod
    def __get_validators__(cls):  # pragma: no cover - used by Pydantic v1
        yield cls._validate

    @classmethod
    def __get_pydantic_core_schema__(  # pragma: no cover - exercised in runtime
        cls,
        _source_type: Any,
        handler: Union["GetCoreSchemaHandler", Any],
    ) -> Any:
        if core_schema is None or GetCoreSchemaHandler is None:
            return handler(str)
        str_schema = core_schema.str_schema()
        return core_schema.no_info_after_validator_function(
            cls._validate,
            str_schema,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(  # pragma: no cover - exercised in runtime
        cls,
        schema: Any,
        handler: Union["GetJsonSchemaHandler", Any],
    ) -> "JsonSchemaValue":
        if JsonSchemaValue is None or GetJsonSchemaHandler is None or core_schema is None:
            return {"type": "string", "title": "SafeAgentID", "minLength": 1}

        str_schema = core_schema.str_schema()
        base_schema = handler(str_schema)
        if isinstance(base_schema, dict):
            base_schema.setdefault("type", "string")
            base_schema.setdefault("title", "SafeAgentID")
            base_schema.setdefault("minLength", 1)
        return base_schema


class InputSanitizer:
    @staticmethod
    def sanitize_path(value: str | Path) -> Path:
        if isinstance(value, str):
            if not value:
                raise ValueError("String should have at least 1 character")
            if "\x00" in value:
                raise ValueError("embedded null character in path")
        path = Path(value)
        if any(part == ".." for part in path.parts):
            raise ValueError("Absolute paths outside allowed directories are not permitted")
        if path.is_absolute():
            return path.resolve()
        base_dir = Path.cwd()
        # In testing environments we allow broader paths for fixtures.
        if not env_detector.is_testing():
            path = (base_dir / path).resolve()
            return path
        return (base_dir / path).resolve()

    @staticmethod
    def sanitize_host_port(value: str) -> Tuple[str, int]:
        if ":" not in value:
            raise ValueError("Host:port format required")
        host, port_str = value.split(":", 1)
        if not host:
            raise ValueError("Invalid hostname format")
        try:
            port = int(port_str)
        except ValueError as exc:
            raise ValueError("Port must be an integer") from exc
        if port <= 0 or port > 65535:
            raise ValueError("Port must be between 1 and 65535")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if host.startswith("-") or ".." in host:
                raise ValueError("Invalid hostname format")
        return host, port

    @staticmethod
    def sanitize_environment_value(name: str, value: str, expected_type: Type[T]) -> T:
        if expected_type is bool:
            lowered = value.lower()
            if lowered in {"true", "1", "yes"}:
                return True  # type: ignore[return-value]
            if lowered in {"false", "0", "no"}:
                return False  # type: ignore[return-value]
            raise ValueError(f"Invalid boolean value for {name}")
        if expected_type is int:
            return int(value)  # type: ignore[return-value]
        if expected_type is float:
            return float(value)  # type: ignore[return-value]
        if expected_type is str:
            return value  # type: ignore[return-value]
        raise TypeError(f"Unsupported type {expected_type!r}")

    @staticmethod
    def validate_path_exists(path: str | Path, *, must_exist: bool = True) -> Path:
        resolved = Path(path).resolve()
        if must_exist and not resolved.exists():
            raise FileNotFoundError(str(resolved))
        return resolved


def sanitize_input(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Input data must be a dictionary")
    return dict(data)


__all__ = ["SafeAgentID", "InputSanitizer", "sanitize_input"]
