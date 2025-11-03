# End-to-End Integration Test Failure: `call_llm` Not Called in `test_complete_user_interaction_flow`

## Summary

The integration test `test_complete_user_interaction_flow` in `tests/test_integration.py` is failing because `call_llm` from `resync.core.ia_auditor` is never invoked, despite the full user interaction flow appearing to execute correctly up to the point of auditor processing. The test verifies that a user message sent via WebSocket triggers a chain including:

1. AgentManager retrieving an agent
2. Agent streaming a response
3. KnowledgeGraph storing the conversation
4. IA Auditor being triggered via `run_auditor_safely`
5. `analyze_and_flag_memories` being called
6. `get_all_recent_conversations` being called on the knowledge graph
7. **`call_llm` being called to perform LLM-based analysis**

The final assertion `mock_llm_call.assert_called()` fails, indicating the LLM was never called during the audit process.

---

## Detailed Flow Analysis

### 1. Test Setup and Mocking

The test mocks the following components:

| Component | Mocked To | Purpose |
|---------|-----------|---------|
| `agent_manager` | `AsyncMock()` | Simulates agent retrieval and streaming |
| `OptimizedTWSClient` | `AsyncMock()` | Mocks TWS client interactions |
| `call_llm` | `AsyncMock()` | Mocks LLM call to detect invocation |
| `analyze_and_flag_memories` | `AsyncMock()` | Mocks main auditor function |
| `AsyncKnowledgeGraph` | `AsyncMock()` | Mocks knowledge graph singleton |
| `audit_queue` | `AsyncMock()` | Mocks audit record queue |
| `connection_manager` | `AsyncMock()` | Mocks WebSocket connection handling |
| `websocket_endpoint` | Direct import | Triggers the actual endpoint logic |

The test correctly:

- Configures `mock_agent.stream` to return an `AsyncIteratorMock` yielding `"Test response from agent"`
- Sets `mock_agent_manager.get_agent.return_value = mock_agent`
- Patches `resync.core.agent_manager.agent_manager` and `resync.api.chat.agent_manager`
- Configures `mock_knowledge_graph_instance` to return a sample conversation when `get_all_recent_conversations()` is called
- Configures `mock_audit_queue.add_audit_record` to be trackable

### 2. Expected Flow vs Actual Behavior

#### ✅ Expected Flow (as intended)

```
WebSocketMessage → websocket_endpoint()
    → agent_manager.get_agent() → Agent.stream() → response streamed to client
    → knowledge_graph.add_conversation() → stores user/agent message
    → asyncio.create_task(run_auditor_safely()) → triggers background audit
        → ia_auditor.analyze_and_flag_memories()
            → knowledge_graph.get_all_recent_conversations()
            → call_llm(prompt) ← 🚫 NEVER CALLED
            → audit_queue.add_audit_record()
```

#### 🚫 Actual Behavior (observed)

- `get_agent called: True` ✅
- `mock_chat_knowledge_graph.add_conversation.assert_called_once()` ✅
- `analyze_and_flag_memories called: False` ❌
- `get_all_recent_conversations called: False` ❌
- `mock_llm_call.assert_called()` ❌ — **Fails**

The **critical failure** is that **neither `analyze_and_flag_memories` nor `get_all_recent_conversations` was called**, even though we waited 2 seconds for the background task to complete.

This implies that `run_auditor_safely()` — the function responsible for triggering the audit — **was never called at all**.

---

## Root Cause: `run_auditor_safely` Is Not Patched

The `/api/chat.py` endpoint contains this code:

```python
# resync/api/chat.py

@router.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    try:
        while True:
            user_message = await websocket.receive_text()
            # ... RAG context retrieval ...
            agent = agent_manager.get_agent(agent_id)
            async for chunk in agent.stream(enhanced_query):
                await websocket.send_text(chunk)
            # Store conversation
            await knowledge_graph.add_conversation(
                user_query=user_message,
                agent_response=full_response,
                agent_id=agent_id,
            )
            # ✅ This is the critical line:
            asyncio.create_task(run_auditor_safely())
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
```

The test patches:

```python
patch("resync.core.ia_auditor.analyze_and_flag_memories")
patch("resync.core.knowledge_graph.AsyncKnowledgeGraph")
patch("resync.core.ia_auditor.call_llm")
```

But **it does NOT patch `run_auditor_safely`**, which is defined in `resync/api/chat.py` and is the **direct caller** of `analyze_and_flag_memories`.

Therefore:

- `run_auditor_safely()` is **not mocked** — it runs the real function
- The real `run_auditor_safely()` function **depends on a real singleton instance** of `ia_auditor`
- The real `ia_auditor.analyze_and_flag_memories()` **calls `call_llm`** — but the real one is not mocked!
- Our `mock_llm_call` is **only a mock for the module-level import** in the test, **not for the real function**
- The real `call_llm` in `resync/core/ia_auditor.py` is **not patched**, so it may be running — but we can't observe it

In this scenario, the test is **patching `call_llm` in the test module**, but the code under test (`run_auditor_safely`) is calling **the real** `call_llm` from `resync.core.ia_auditor`, which is **not mocked**.

Thus, `mock_llm_call` remains un-called → assertion fails.

---

## Why Is `analyze_and_flag_memories` Also Not Called?

Because `run_auditor_safely()` is **not mocked**, it’s executing the real function. But the real function is in `resync/api/chat.py`, which is **not patched**.

The real `run_auditor_safely()` contains:

```python
# resync/api/chat.py

async def run_auditor_safely():
    try:
        await ia_auditor.analyze_and_flag_memories()
    except Exception as e:
        logger.error(f"Auditor failed: {e}")
```

The test **does not patch `run_auditor_safely`** in `resync/api/chat.py`, so the **real function runs**.

But the real function calls `ia_auditor.analyze_and_flag_memories()`, which **is patched** — so we should see `mock_analyze_and_flag_memories.called == True`.

Yet we see `False`.

This implies that the **real `run_auditor_safely()` is not being called at all** — meaning `asyncio.create_task(run_auditor_safely())` is **not being executed**.

However, `websocket_endpoint` is called, and the message is received — so why isn’t `create_task` called?

We added debug prints before and after the `create_task` call, and they were never logged — suggesting the code path **never reaches** `create_task`.

But we see `add_conversation.assert_called_once()` — meaning the stream **did complete**.

This is a contradiction.

### Hypothesis: WebSocket Disconnects Before `create_task` Is Reached

The test simulates:

```python
async def mock_receive_text():
    if message_count == 0:
        message_count += 1
        return "How do I restart a job in TWS?"
    else:
        raise WebSocketDisconnect(code=1000, reason="Client disconnected")
```

The `async for` loop over `agent.stream()` is **blocking** — if the agent stream never terminates (e.g., due to async iterator not yielding properly), the `create_task` line is never reached.

But we see `Stream method verification skipped for function-based mock` — confirming the stream returned a value.

However, if the stream **never terminates**, the `async for` loop hangs indefinitely, and the next line (`add_conversation`) is never reached — much less `create_task`.

But we see `add_conversation.assert_called_once()` — meaning the stream **did complete**.

Thus, `create_task` should have been called.

### Final Conclusion: `run_auditor_safely` Is Not Patched → Real Function Runs → Real Function Uses Real `ia_auditor` → Real `ia_auditor` Uses Real `call_llm` → Mock Is Never Called

The **primary issue** is that the test **patches `call_llm` in the test module**, but the **code under test** (`run_auditor_safely`) is calling **the real `call_llm`** from `resync.core.ia_auditor`, **not the patched version**.

This is a classic **patching scope mismatch**.

---

## Corrective Actions Required

### ✅ Immediate Fix: Patch `run_auditor_safely` in `resync.api.chat`

Add this patch in the test:

```python
patch("resync.api.chat.run_auditor_safely") as mock_run_auditor_safely
```

Then verify:

```python
assert mock_run_auditor_safely.called
```

### ✅ Patch `ia_auditor.analyze_and_flag_memories` — Already Done

✅ Already patched — but won’t help if `run_auditor_safely` doesn't call it.

### ✅ Patch `resync.core.ia_auditor.call_llm`, not `resync.core.ia_auditor.call_llm` in test context

We are currently patching `mock_llm_call` as if it were the same as `resync.core.ia_auditor.call_llm`. But we must patch **the actual import site**.

Change this:

```python
patch("resync.core.ia_auditor.call_llm", mock_llm_call)
```

To **patch the module where `run_auditor_safely` imports it** — which is `resync.core.ia_auditor`.

We are already doing that — so if `run_auditor_safely` were called, this would work.

Thus, the **real blocker** is: `run_auditor_safely` is **not being called**.

### ✅ Why Isn't `run_auditor_safely` Called?

Possibility: `asyncio.create_task(run_auditor_safely())` is **executed**, but the task **is canceled or garbage collected** because the WebSocket disconnects and the test exits before the task runs.

Add an `await asyncio.sleep(0.1)` after `create_task` to let the event loop schedule the task.

Or better: **patch `run_auditor_safely` and assert it was called directly**, then simulate its behavior.

### ✅ Recommended Fix

1. Patch `resync.api.chat.run_auditor_safely`
2. Use `AsyncMock()` to mock it
3. Assert it was called
4. **Manually invoke** the real `analyze_and_flag_memories` via `mock_run_auditor_safely.side_effect = lambda: asyncio.create_task(ia_auditor.analyze_and_flag_memories())` — but since we’re testing integration, we want to simulate the call.

Better: **Let the real `run_auditor_safely` run, but patch `ia_auditor.analyze_and_flag_memories` and `call_llm` in `resync.core.ia_auditor`**.

But we already are — so why isn't it working?

Wait — we are patching `resync.core.ia_auditor.analyze_and_flag_memories` — that’s correct.

We are patching `resync.core.ia_auditor.call_llm` — that’s correct.

We are **not** patching `resync.api.chat.run_auditor_safely` — so the real function runs, which calls the **real** `ia_auditor` — which uses the **real** `call_llm` — which is **not** the mock.

But we **did** patch `resync.core.ia_auditor.call_llm` — so it should work.

Unless… there’s a **circular import or module caching issue**.

### 💡 Final Diagnostic: Print Module Path of `call_llm` in Test

Add this before the assertion:

```python
import resync.core.ia_auditor
print(f"Real call_llm module: {resync.core.ia_auditor.call_llm}")
print(f"Mock is same object? {mock_llm_call is resync.core.ia_auditor.call_llm}")
```

If output is `False`, then the patching failed due to module caching or import order.

This is likely the case.

---

## Recommended Resolution

### ✅ Step 1: Patch `run_auditor_safely` in `resync.api.chat`

```python
with (
    ...
    patch("resync.api.chat.run_auditor_safely") as mock_run_auditor_safely,
    patch("resync.core.ia_auditor.analyze_and_flag_memories") as mock_analyze_and_flag_memories,
    patch("resync.core.ia_auditor.call_llm", mock_llm_call),
    ...
):
```

### ✅ Step 2: Assert `run_auditor_safely` was called

```python
assert mock_run_auditor_safely.called, "run_auditor_safely was not called!"
```

### ✅ Step 3: Simulate auditor behavior inside mock (optional)

```python
async def real_auditor():
    await ia_auditor.analyze_and_flag_memories()

mock_run_auditor_safely.side_effect = real_auditor
```

### ✅ Step 4: Ensure `call_llm` is patched in the **correct module**

Use `patch("resync.core.ia_auditor.call_llm")` — this is correct.

### ✅ Step 5: Add debug print to verify patching worked

```python
import resync.core.ia_auditor
print(f"call_llm patched? {resync.core.ia_auditor.call_llm is mock_llm_call}")
```

If output is `False`, patching failed — use `patch.object` instead:

```python
patch.object(resync.core.ia_auditor, "call_llm", mock_llm_call)
```



