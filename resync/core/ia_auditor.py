"""IA auditor compatibility layer.

This shim keeps the public API depended upon by the FastAPI routes and unit
tests without pulling in the legacy implementation.  Each helper mirrors the
original behaviour at a coarse level (lock cleanup, knowledge graph queries,
LLM parsing) while remaining intentionally lightweight.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from resync.core.exceptions import DatabaseError, LLMError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight dependency shims
# ---------------------------------------------------------------------------
class _AuditLock:
    """Wrapper adding ``cleanup_expired_locks`` to a standard asyncio.Lock."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "_AuditLock":
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._lock.locked():
            self._lock.release()

    async def cleanup_expired_locks(self) -> None:
        """Placeholder for backward compatibility."""
        return None


class _KnowledgeGraphStub:
    async def get_all_recent_conversations(self) -> List[Dict[str, Any]]:
        return []

    async def delete_memory(self, memory_id: str) -> None:
        return None

    async def is_memory_already_processed(self, memory_id: str) -> bool:
        return False

    async def is_memory_flagged(self, memory_id: str) -> bool:
        return False

    async def is_memory_approved(self, memory_id: str) -> bool:
        return False


class _AuditQueueStub:
    async def add_audit_record(self, action: str, payload: Any) -> bool:
        return True


audit_lock: _AuditLock = _AuditLock()
knowledge_graph: _KnowledgeGraphStub = _KnowledgeGraphStub()
audit_queue: _AuditQueueStub = _AuditQueueStub()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
async def _cleanup_locks() -> None:
    """Run periodic cleanup of distributed locks with defensive logging."""
    cleanup = getattr(audit_lock, "cleanup_expired_locks", None)
    if cleanup is None:
        return
    try:
        result = cleanup()
        if asyncio.iscoroutine(result):
            await result
    except Exception:  # pragma: no cover - defensive
        logger.warning("Failed to cleanup auditor locks", exc_info=True)


async def _fetch_recent_memories() -> Optional[List[Dict[str, Any]]]:
    """Fetch recent memories from the knowledge graph."""
    try:
        memories = await knowledge_graph.get_all_recent_conversations()
    except DatabaseError:
        return None
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected error fetching memories", exc_info=True)
        return None
    return memories


async def _validate_memory_for_analysis(memory: Dict[str, Any]) -> bool:
    """Basic validation to prevent empty entries from being analysed."""
    required_keys = {"id", "user_query", "agent_response"}
    if not required_keys.issubset(memory):
        return False
    return True


def call_llm(*args: Any, **kwargs: Any) -> str:
    """Placeholder LLM invocation returning a deterministic payload."""
    prompt = kwargs.get("prompt", "")
    return json.dumps({"action": "noop", "payload": prompt})


def parse_llm_json_response(response: str) -> Dict[str, Any]:
    """Parse the JSON response returned by :func:`call_llm`."""
    if not response:
        return {"action": "noop", "payload": None}
    try:
        data = json.loads(response)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"action": "noop", "payload": None}


async def analyze_memory(memory: Dict[str, Any]) -> Optional[Tuple[str, Any]]:
    """Analyse a memory entry and return an action tuple or ``None``."""
    async with audit_lock:
        if not await _validate_memory_for_analysis(memory):
            return None

        memory_id = memory.get("id")
        if memory_id:
            if await knowledge_graph.is_memory_already_processed(memory_id):
                return None
            if await knowledge_graph.is_memory_flagged(memory_id):
                return None
            if await knowledge_graph.is_memory_approved(memory_id):
                return None

        try:
            response = call_llm(
                prompt=memory.get("user_query", ""),
                agent_response=memory.get("agent_response", ""),
                metadata={"id": memory_id},
            )
        except LLMError:
            return None

        parsed = parse_llm_json_response(response)
        action = parsed.get("action")
        payload = parsed.get("payload")

        if action == "delete":
            return ("delete", payload or memory_id)
        if action == "flag":
            return ("flag", payload or memory)
        return None


async def _analyze_memories_concurrently(
    memories: Sequence[Dict[str, Any]]
) -> List[Optional[Tuple[str, Any]]]:
    tasks = [asyncio.create_task(analyze_memory(memory)) for memory in memories]
    if not tasks:
        return []
    return await asyncio.gather(*tasks)


async def _process_analysis_results(
    results: Iterable[Optional[Tuple[str, Any]]]
) -> Tuple[List[str], List[Any]]:
    """Split analysis results into delete/flag lists while enqueuing audits."""
    to_delete: List[str] = []
    to_flag: List[Any] = []

    for result in results:
        if not result:
            continue
        action, payload = result
        try:
            await audit_queue.add_audit_record(action, payload)
        except Exception:  # pragma: no cover - defensive logging
            logger.warning("Failed to enqueue audit record", exc_info=True)

        if action == "delete":
            if isinstance(payload, dict):
                memory_id = payload.get("id")
                if memory_id:
                    to_delete.append(memory_id)
            elif isinstance(payload, str):
                to_delete.append(payload)
        elif action == "flag":
            to_flag.append(payload)

    return to_delete, to_flag


async def analyze_and_flag_memories() -> Dict[str, Any]:
    """Entry point orchestrating the full auditing workflow."""
    await _cleanup_locks()
    memories = await _fetch_recent_memories()

    if memories is None:
        return {"deleted": 0, "flagged": 0, "error": "database_fetch_failed"}
    if not memories:
        return {"deleted": 0, "flagged": 0}

    results = await _analyze_memories_concurrently(memories)
    to_delete, to_flag = await _process_analysis_results(results)

    deleted = 0
    for memory_id in to_delete:
        if not memory_id:
            continue
        try:
            await knowledge_graph.delete_memory(memory_id)
            deleted += 1
        except Exception:  # pragma: no cover - defensive logging
            logger.warning("Failed to delete memory '%s'", memory_id, exc_info=True)

    return {"deleted": deleted, "flagged": len(to_flag)}


__all__ = [
    "audit_lock",
    "knowledge_graph",
    "audit_queue",
    "_cleanup_locks",
    "_fetch_recent_memories",
    "_validate_memory_for_analysis",
    "_analyze_memories_concurrently",
    "_process_analysis_results",
    "analyze_memory",
    "analyze_and_flag_memories",
    "call_llm",
    "parse_llm_json_response",
]
