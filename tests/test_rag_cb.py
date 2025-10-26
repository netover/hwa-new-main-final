import pytest
import httpx
from resync.services.rag_client import RAGServiceClient
from resync.core.resilience import CircuitBreakerError


@pytest.mark.asyncio
async def test_cb_opens(monkeypatch):
    client = RAGServiceClient()

    async def always_fails(*a, **k):
        raise httpx.RequestError("boom")
    monkeypatch.setattr(client.http_client, "post", always_fails)
    monkeypatch.setattr(client.http_client, "get", always_fails)

    # Make one call that will fail 3 times and open the circuit breaker
    with pytest.raises(httpx.RequestError):
        await client.get_job_status("job-1")

    # After 5+ failures, CB should be open and next call should fail-fast
    with pytest.raises(CircuitBreakerError):
        await client.get_job_status("job-1")  # CB is open, fail-fast


@pytest.mark.asyncio
async def test_retry_with_jitter(monkeypatch):
    calls = {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.TimeoutException("timeout")
        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"job_id": "x", "status": "done"}
        return Resp()

    client = RAGServiceClient()
    monkeypatch.setattr(client.http_client, "post", flaky)
    monkeypatch.setattr(client.http_client, "get", flaky)
    result = await client.get_job_status("x")
    assert result.status == "done"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_enqueue_file_retry(monkeypatch):
    calls = {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.TimeoutException("timeout")
        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"job_id": "x"}
        return Resp()

    client = RAGServiceClient()
    monkeypatch.setattr(client.http_client, "post", flaky)
    job_id = await client.enqueue_file(type("File", (), {"filename": "test.txt", "file": "content", "content_type": "text/plain"})())
    assert job_id == "x"
    assert calls["n"] == 3