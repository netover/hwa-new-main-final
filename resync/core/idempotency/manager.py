"""Redis-backed idempotency primitives used by the FastAPI middleware."""

from __future__ import annotations

import asyncio
import json
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def generate_idempotency_key() -> str:
    """Return a new UUID4 idempotency key."""
    return str(uuid.uuid4())


def validate_idempotency_key(value: str | None) -> bool:
    """Validate that the supplied value matches the UUID4 format."""
    if not value:
        return False
    return bool(UUID_PATTERN.match(value))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class IdempotencyConfig:
    """Runtime configuration for the :class:`IdempotencyManager`."""

    ttl_hours: int = 24
    key_prefix: str = "idempotency:response"
    processing_prefix: str = "idempotency:processing"
    max_payload_kb: int = 64
    processing_ttl_seconds: int = 300

    @property
    def ttl_seconds(self) -> int:
        return max(60, int(self.ttl_hours * 3600))


@dataclass(slots=True)
class IdempotencyRecord:
    """Serialized representation of a cached response."""

    idempotency_key: str
    request_hash: str | None
    response_data: dict[str, Any]
    status_code: int
    created_at: datetime
    expires_at: datetime
    request_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "idempotency_key": self.idempotency_key,
            "request_hash": self.request_hash,
            "response_data": self.response_data,
            "status_code": self.status_code,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "request_metadata": self.request_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdempotencyRecord":
        return cls(
            idempotency_key=data["idempotency_key"],
            request_hash=data.get("request_hash"),
            response_data=data.get("response_data", {}),
            status_code=data.get("status_code", 200),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            request_metadata=data.get("request_metadata") or {},
        )


class IdempotencyManager:
    """Store idempotency records using an asynchronous Redis client."""

    def __init__(self, redis_client: Any, config: IdempotencyConfig | None = None) -> None:
        self._redis = redis_client
        self.config = config or IdempotencyConfig()

        # Metrics
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._concurrent_blocks = 0
        self._storage_errors = 0
        self._expired_cleanups = 0

        # Redis operations can be patched for tests; keep lock for concurrent updates
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ utils
    def _response_key(self, idempotency_key: str) -> str:
        return f"{self.config.key_prefix}:{idempotency_key}"

    def _processing_key(self, idempotency_key: str) -> str:
        return f"{self.config.processing_prefix}:{idempotency_key}"

    def _serialize(self, record: IdempotencyRecord) -> str:
        return json.dumps(record.to_dict(), separators=(",", ":"), default=str)

    def _deserialize(self, payload: str) -> IdempotencyRecord:
        data = json.loads(payload)
        return IdempotencyRecord.from_dict(data)

    def _payload_size_ok(self, data: dict[str, Any]) -> bool:
        size_kb = len(json.dumps(data).encode()) / 1024
        return size_kb <= self.config.max_payload_kb

    # ------------------------------------------------------------------ public
    async def get_cached_response(
        self,
        idempotency_key: str,
        request_signature: Any | None = None,
    ) -> Optional[dict[str, Any]]:
        """Retrieve a cached response for the supplied idempotency key."""
        async with self._lock:
            self._total_requests += 1

        try:
            cached = await self._redis.get(self._response_key(idempotency_key))
        except Exception:
            self._storage_errors += 1
            return None

        if not cached:
            self._cache_misses += 1
            return None

        try:
            record = self._deserialize(cached)
        except Exception:
            self._storage_errors += 1
            return None

        if record.expires_at < _utcnow():
            self._expired_cleanups += 1
            await self._redis.delete(self._response_key(idempotency_key))
            self._cache_misses += 1
            return None

        self._cache_hits += 1
        return {
            "status_code": record.status_code,
            "data": record.response_data,
            "cached_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "request_metadata": record.request_metadata,
        }

    async def cache_response(
        self,
        *,
        idempotency_key: str,
        response_data: dict[str, Any],
        status_code: int,
        request_hash: str | None = None,
        request_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Persist a response for future reuse."""
        if not self._payload_size_ok(response_data):
            return False

        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response_data=response_data,
            status_code=status_code,
            created_at=_utcnow(),
            expires_at=_utcnow() + timedelta(seconds=self.config.ttl_seconds),
            request_metadata=request_metadata or {},
        )

        try:
            await self._redis.setex(
                self._response_key(idempotency_key),
                self.config.ttl_seconds,
                self._serialize(record),
            )
        except Exception:
            self._storage_errors += 1
            return False
        return True

    async def is_processing(self, idempotency_key: str) -> bool:
        """Return ``True`` if the key is currently marked as processing."""
        try:
            exists = await self._redis.exists(
                self._processing_key(idempotency_key)
            )
            if exists:
                self._concurrent_blocks += 1
            return bool(exists)
        except Exception:
            self._storage_errors += 1
            return False

    async def mark_processing(
        self,
        idempotency_key: str,
        *,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Mark a key as currently being processed."""
        ttl = ttl_seconds or self.config.processing_ttl_seconds
        payload = {
            "started_at": _utcnow().isoformat(),
            "ttl_seconds": ttl,
        }
        try:
            return bool(
                await self._redis.setex(
                    self._processing_key(idempotency_key),
                    ttl,
                    json.dumps(payload),
                )
            )
        except Exception:
            self._storage_errors += 1
            return False

    async def clear_processing(self, idempotency_key: str) -> bool:
        """Clear processing marker for a key."""
        try:
            deleted = await self._redis.delete(
                self._processing_key(idempotency_key)
            )
            return bool(deleted)
        except Exception:
            self._storage_errors += 1
            return False

    async def invalidate_key(self, idempotency_key: str) -> bool:
        """Invalidate both cached response and processing marker."""
        try:
            deleted = await self._redis.delete(
                self._response_key(idempotency_key),
                self._processing_key(idempotency_key),
            )
            return bool(deleted)
        except Exception:
            self._storage_errors += 1
            return False

    def get_metrics(self) -> dict[str, float | int]:
        """Return current idempotency metrics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total) if total else 0.0
        return {
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": round(hit_rate, 4),
            "concurrent_blocks": self._concurrent_blocks,
            "storage_errors": self._storage_errors,
            "expired_cleanups": self._expired_cleanups,
        }


__all__ = [
    "IdempotencyConfig",
    "IdempotencyManager",
    "IdempotencyRecord",
    "generate_idempotency_key",
    "validate_idempotency_key",
]
