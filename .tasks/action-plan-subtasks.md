# Resync: Action Plan for Performance, Stability, and Scalability Improvements

This document details the complete set of subtasks derived from the comprehensive architectural analysis. Each subtask is specific, actionable, and designed to be independently executed by a developer or a team in Code mode.

## Subtask 1: [HIGH] Fix Race Condition in IA Auditor

**Objective**: Ensure the IA Auditor's state management is atomic, preventing duplicate flagging of the same memory.

**Action Steps**:
1. In `resync/core/knowledge_graph.py`, add a new method `is_memory_flagged(self, memory_id: str) -> bool` that uses `self.client.search(f"metadata:FLAGGED_BY_IA AND id:{memory_id}", limit=1)`.
2. In `resync/core/ia_auditor.py`, replace the current `if any("FLAGGED_BY_IA" in str(obs) for obs in observations)` check with a call to `knowledge_graph.is_memory_flagged(mem["id"])`.
3. Remove the code that checks for `MANUALLY_APPROVED_BY_ADMIN` from the observations, as the `audit_queue` database now serves as the source of truth for human approval.
4. In `resync/core/audit_db.py`, add a new method `is_memory_approved(self, memory_id: str) -> bool` that queries the `audit_queue` table for a record with `status = 'approved'` and `memory_id = ?`.
5. Modify the `analyze_memory` function in `ia_auditor.py` to skip any memory that is either flagged by the IA or approved by a human, using the new methods.

**Output**: Updated `resync/core/knowledge_graph.py`, `resync/core/ia_auditor.py`, and `resync/core/audit_db.py`.

## Subtask 2: [HIGH] Refactor Knowledge Graph to use truly async Mem0 client

**Objective**: Eliminate any potential blocking I/O within the Knowledge Graph by ensuring all Mem0 AI interactions are non-blocking.

**Action Steps**:
1. Research the Mem0 AI Python SDK documentation to determine if its `search`, `add`, and `add_observations` methods are truly asynchronous or if they internally use blocking HTTP calls.
2. If Mem0's methods are blocking, create a new class `AsyncKnowledgeGraph` in `resync/core/knowledge_graph.py`, inheriting from `KnowledgeGraph`.
3. Override all public methods (`add_conversation`, `search_similar_issues`, `get_all_recent_conversations`, `add_solution_feedback`, `get_relevant_context`) to use `asyncio.run_in_executor` to wrap the underlying Mem0 client calls.
4. Replace the global `knowledge_graph = KnowledgeGraph()` instance with `knowledge_graph = AsyncKnowledgeGraph()`.
5. Update all imports in `ia_auditor.py`, `chat.py`, and `audit.py` to import `AsyncKnowledgeGraph` as `knowledge_graph`.
6. Add a new test in `tests/test_knowledge_graph.py` to verify that the methods do not block the event loop.

**Output**: `resync/core/knowledge_graph.py` with `AsyncKnowledgeGraph` class and updated global instance.

## Subtask 3: [HIGH] Document TWS Client SSL Configuration Decision

**Objective**: Document the decision to maintain current SSL verification settings for development environments.

**Action Steps**:
1. Update documentation to reflect that `verify=False` should be maintained for development environments.
2. Document the rationale for keeping SSL verification disabled in the current setup.
3. Ensure no changes are made to the existing `httpx.AsyncClient` configuration.

**Output**: Updated `architecture-optimization-plan.md` with SSL configuration decision.

## Subtask 4: [MEDIUM] Replace SQLite with a scalable database for audit queue

**Objective**: Replace the SQLite database with a high-concurrency, scalable database to handle the audit queue under load.

**Action Steps**:
1. Evaluate the performance and scalability requirements. Choose between PostgreSQL (for full SQL features) or Redis (for speed and simplicity).
2. Install the database driver (e.g., `psycopg2-binary` for PostgreSQL or `redis-py` for Redis).
3. Create a new module `resync/core/audit_queue.py` with a new class `AuditQueue` that provides the same interface as the current `audit_db` module (methods: `add_audit_record`, `get_pending_audits`, `update_audit_status`, `delete_audit_record`).
4. Implement the `AuditQueue` class using the chosen database.
5. Update all imports in `ia_auditor.py` to use `from resync.core.audit_queue import add_audit_record` instead of `from resync.core import audit_db`.
6. Write a migration script in `scripts/migrate_audit_db.py` to transfer existing data from `audit_queue.db` to the new database.

**Output**: `resync/core/audit_queue.py`, migration script, and updated `requirements.txt`.

## Subtask 5: [MEDIUM] Implement Async Lock for Agent Manager TWS Client Initialization

**Objective**: Prevent race conditions during TWS client initialization in the AgentManager.

**Action Steps**:
1. In `resync/core/agent_manager.py`, add an `asyncio.Lock` instance as a class attribute: `self._tws_client_lock = asyncio.Lock()`.
2. In the `_get_tws_client()` method, wrap the client initialization block in an `async with self._tws_client_lock:` context manager.
3. Ensure the lock is initialized in `__init__` if `self._initialized` is `False`.
4. Add a unit test in `tests/test_agent_manager.py` that simulates 5 concurrent calls to `_get_tws_client()` and verifies only one client is created.

**Output**: Updated `resync/core/agent_manager.py` and `tests/test_agent_manager.py`.

## Subtask 6: [LOW] Increase LLM Prompt `max_tokens` for IA Auditor

**Objective**: Ensure the IA Auditor's LLM has sufficient context to generate complete and accurate analyses.

**Action Steps**:
1. In `resync/core/ia_auditor.py`, locate the `call_llm` function call within the `analyze_memory` function.
2. Change the `max_tokens=200` parameter to `max_tokens=500`.
3. Verify the LLM endpoint supports the increased token limit.
4. Add a comment in the code explaining the reason for the increased limit.

**Output**: Updated `resync/core/ia_auditor.py`.



