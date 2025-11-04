from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Optional

try:  # pragma: no cover - optional dependency during tests
    import redis.asyncio as redis  # type: ignore
    from redis.exceptions import ResponseError
except Exception:  # pragma: no cover - defensive fallback
    redis = None  # type: ignore
    ResponseError = Exception  # type: ignore

from resync.core.exceptions import AuditError, DatabaseError

LOGGER = logging.getLogger("resync.audit.lock")

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


@dataclass
class AuditLockContext:
    client: Any
    lock_key: str
    timeout: int
    release_script_sha: str
    lock_value: str
    _locked: bool = False

    async def _acquire(self) -> None:
        LOGGER.debug("Acquiring audit lock: %s", self.lock_key)
        ok = await self.client.set(
            self.lock_key,
            self.lock_value,
            nx=True,
            px=self.timeout * 1000,
        )
        if not ok:
            raise AuditError("Could not acquire audit lock")
        self._locked = True

    async def __aenter__(self) -> "AuditLockContext":
        if not self._locked:
            await self._acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._release_lock()

    async def _release_lock(self) -> None:
        if not self._locked:
            return
        try:
            await self.client.evalsha(
                self.release_script_sha,
                1,
                self.lock_key,
                self.lock_value,
            )
        except ResponseError:
            LOGGER.warning("Release script missing, using EVAL fallback")
            try:
                await self.client.eval(
                    _RELEASE_SCRIPT,
                    1,
                    self.lock_key,
                    self.lock_value,
                )
            except Exception as exc:  # pragma: no cover - defensive
                raise DatabaseError("Failed to release audit lock") from exc
        finally:
            self._locked = False


class DistributedAuditLock:
    def __init__(self, redis_url: str, *, prefix: str = "audit_lock") -> None:
        self.redis_url = redis_url
        self.prefix = prefix
        self.client: Any | None = None
        self.release_script_sha: str | None = None

    async def connect(self) -> None:
        if redis is None:
            raise RuntimeError("redis.asyncio is required for DistributedAuditLock")
        self.client = redis.from_url(self.redis_url)
        self.release_script_sha = await self.client.script_load(_RELEASE_SCRIPT)

    async def disconnect(self) -> None:
        if self.client is not None:
            try:
                await self.client.close()
            except Exception:  # pragma: no cover - defensive
                LOGGER.debug("Failed to close redis client", exc_info=True)
            self.client = None
            self.release_script_sha = None

    def _ensure_client(self) -> Any:
        if self.client is None or self.release_script_sha is None:
            raise RuntimeError("Audit lock not connected")
        return self.client

    def _get_lock_key(self, memory_id: str) -> str:
        if not isinstance(memory_id, str) or not memory_id:
            raise ValueError("Invalid memory_id - must be a non-empty string")
        return f"{self.prefix}:{memory_id}"

    async def acquire(self, memory_id: str, timeout: int = 30) -> AuditLockContext:
        client = self._ensure_client()
        lock_key = self._get_lock_key(memory_id)
        lock_value = str(uuid.uuid4())
        context = AuditLockContext(
            client=client,
            lock_key=lock_key,
            timeout=timeout,
            release_script_sha=self.release_script_sha,  # type: ignore[arg-type]
            lock_value=lock_value,
        )
        await context._acquire()
        return context

    async def force_release(self, memory_id: str) -> None:
        client = self._ensure_client()
        lock_key = self._get_lock_key(memory_id)
        await client.delete(lock_key)

    async def is_locked(self, memory_id: str) -> bool:
        client = self._ensure_client()
        lock_key = self._get_lock_key(memory_id)
        exists = await client.exists(lock_key)
        return bool(exists)

    async def cleanup_expired_locks(self, *, max_age: int = 30) -> None:
        client = self._ensure_client()
        pattern = f"{self.prefix}:*"
        keys: Iterable[str] = await client.keys(pattern)
        for key in keys:
            ttl = await client.ttl(key)
            if ttl == -2:
                await client.delete(key)
            elif ttl == -1 and max_age >= 0:
                await client.delete(key)


__all__ = ["DistributedAuditLock", "AuditLockContext"]
