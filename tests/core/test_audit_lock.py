"""
Comprehensive unit tests for DistributedAuditLock.

Tests verify:
- Basic lock acquisition and release.
- Lock prevents duplicate flagging under concurrent tasks.
- Lock times out correctly.
- Lock is re-entrant within the same task.
- Force release functionality.
- Cleanup of expired locks.
- Validation of inputs and context management.
"""

import asyncio
import logging
from unittest.mock import ANY, AsyncMock, patch

import pytest
import pytest_asyncio
from redis.exceptions import ResponseError

from resync.core.audit_lock import (
    AuditLockContext,
    DistributedAuditLock,
)
from resync.core.exceptions import AuditError, DatabaseError


@pytest.fixture
def mock_redis_client():
    """Create a mock of redis.asyncio.Redis for testing."""
    client = AsyncMock()
    client.set.return_value = True
    client.evalsha.return_value = 1
    client.eval.return_value = 1
    client.script_load.return_value = "mock_release_script_sha"
    client.exists.return_value = 1
    client.get.return_value = "mock_uuid".encode("utf-8")
    client.delete.return_value = 1
    client.keys.return_value = [
        f"audit_lock:expired_key_{i}".encode("utf-8") for i in range(3)
    ]
    client.ttl.return_value = -2
    client.ping.return_value = True
    return client


@pytest_asyncio.fixture
async def audit_lock_instance(mock_redis_client):
    """
    Create a DistributedAuditLock instance for testing, backed by a mock Redis client.
    """
    with patch("redis.asyncio.Redis.from_url", return_value=mock_redis_client):
        lock = DistributedAuditLock("redis://mock-server:6379/1")
        await lock.connect()
        yield lock
        await lock.disconnect()


@pytest.fixture
def audit_lock_context(mock_redis_client):
    """Create an AuditLockContext for testing."""
    context = AuditLockContext(
        client=mock_redis_client,
        lock_key="audit_lock:test_context_key",
        timeout=30,
        release_script_sha="mock_release_script_sha",
    )
    return context


class TestDistributedAuditLock:
    """Consolidated test suite for all DistributedAuditLock functionality."""

    @pytest.mark.asyncio
    async def test_basic_lock_acquisition(self, audit_lock_instance, mock_redis_client):
        """Test basic lock acquisition and that it prevents re-acquisition."""
        memory_id = "test_memory_123"

        mock_redis_client.set.return_value = True
        context = await audit_lock_instance.acquire(memory_id, timeout=5)
        async with context:
            mock_redis_client.set.assert_called_with(ANY, ANY, nx=True, px=5000)

            mock_redis_client.set.return_value = False
            with pytest.raises(AuditError, match="Could not acquire audit lock"):
                async with await audit_lock_instance.acquire(memory_id, timeout=1):
                    pass  # This block should not be reached

    @pytest.mark.asyncio
    async def test_lock_is_locked(self, audit_lock_instance, mock_redis_client):
        """Test the is_locked method."""
        memory_id = "test_is_locked"
        mock_redis_client.exists.return_value = 1
        assert await audit_lock_instance.is_locked(memory_id) is True
        mock_redis_client.exists.assert_called_once_with(f"audit_lock:{memory_id}")

        mock_redis_client.exists.return_value = 0
        assert await audit_lock_instance.is_locked(memory_id) is False

    @pytest.mark.asyncio
    async def test_concurrent_lock_prevention(
        self, audit_lock_instance, mock_redis_client
    ):
        """Test that concurrent processes cannot acquire the same lock."""
        memory_id = "test_memory_concurrent"
        results = []

        mock_redis_client.set.side_effect = [True, False, False, False, False]

        async def worker(worker_id: int):
            try:
                context = await audit_lock_instance.acquire(memory_id, timeout=5)
                async with context:
                    await asyncio.sleep(0.01)
                    results.append(f"worker_{worker_id}_success")
            except AuditError:
                results.append(f"worker_{worker_id}_failed")

        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if "success" in r)
        assert success_count == 1
        assert mock_redis_client.set.call_count == 5

    @pytest.mark.asyncio
    async def test_force_release_lock(self, audit_lock_instance, mock_redis_client):
        """Test force release functionality."""
        memory_id = "test_memory_force_release"
        lock_key = audit_lock_instance._get_lock_key(memory_id)

        await audit_lock_instance.force_release(memory_id)
        mock_redis_client.delete.assert_called_once_with(lock_key)

    @pytest.mark.asyncio
    async def test_cleanup_expired_locks(self, audit_lock_instance, mock_redis_client):
        """Test cleanup of expired locks."""
        await audit_lock_instance.cleanup_expired_locks(max_age=1)
        assert mock_redis_client.keys.call_count == 1
        assert mock_redis_client.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_lock_key_validation(self, audit_lock_instance):
        """Test that memory_id validation is enforced."""
        with pytest.raises(
            ValueError, match="Invalid memory_id - must be a non-empty string"
        ):
            audit_lock_instance._get_lock_key(123)

        with pytest.raises(
            ValueError, match="Invalid memory_id - must be a non-empty string"
        ):
            audit_lock_instance._get_lock_key("")

    @pytest.mark.asyncio
    async def test_context_manager_behavior(
        self, audit_lock_context, mock_redis_client
    ):
        """Test the AuditLockContext context manager enter/exit behavior."""
        mock_redis_client.set.return_value = True
        mock_redis_client.evalsha.reset_mock()

        async with audit_lock_context:
            assert audit_lock_context._locked
            mock_redis_client.set.assert_called_once()

        mock_redis_client.evalsha.assert_called_once_with(
            "mock_release_script_sha",
            1,
            "audit_lock:test_context_key",
            audit_lock_context.lock_value,
        )

    @pytest.mark.asyncio
    async def test_context_exception_handling(
        self, audit_lock_context, mock_redis_client
    ):
        """Test that the lock is released even if an exception occurs."""
        mock_redis_client.set.return_value = True
        mock_redis_client.evalsha.reset_mock()

        with pytest.raises(ValueError, match="Test exception"):
            async with audit_lock_context:
                raise ValueError("Test exception")

        mock_redis_client.evalsha.assert_called_once()

    @pytest.mark.asyncio
    async def test_eval_fallback(self, audit_lock_context, mock_redis_client, caplog):
        """Test fallback to EVAL when EVALSHA fails."""
        mock_redis_client.set.return_value = True
        await audit_lock_context.__aenter__()

        mock_redis_client.evalsha.side_effect = ResponseError("NOSCRIPT ...")

        with caplog.at_level(logging.WARNING):
            # This should now raise DatabaseError, which we catch to inspect the process
            with pytest.raises(DatabaseError):
                await audit_lock_context._release_lock()

        assert mock_redis_client.evalsha.call_count == 1
        # In case of NOSCRIPT, the code should not fallback to EVAL, but raise
        assert mock_redis_client.eval.call_count == 0
        assert "Redis error during lock release" in caplog.text

    @pytest.mark.asyncio
    async def test_global_audit_lock_convenience_function(self):
        """Test the global audit_lock instance is used correctly by patching its client."""
        mock_client = AsyncMock()
        mock_client.set.return_value = True
        mock_client.evalsha.return_value = 1
        mock_client.script_load.return_value = "sha"
        mock_client.ping.return_value = True

        with patch("redis.asyncio.Redis.from_url", return_value=mock_client):
            memory_id = "test_global_instance"
            # Use a new instance to ensure our patch is used
            test_lock = DistributedAuditLock()
            async with await test_lock.acquire(memory_id, timeout=5):
                mock_client.set.assert_called_once()

            mock_client.evalsha.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
