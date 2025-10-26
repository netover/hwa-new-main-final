"""
Simple test for circuit breaker implementation.

This test validates that the circuit breaker decorator works properly.
"""

import pytest

from resync.core.circuit_breakers import redis_breaker
from resync.core.exceptions import RedisConnectionError

# Configure logger for testing


class TestCircuitBreakerSimple:
    """Simple test for circuit breaker implementation."""
    
    @pytest.mark.asyncio
    async def test_redis_circuit_breaker_simple(self):
        """Test that Redis circuit breaker works with a simple function."""
        # Create a mock function that raises RedisConnectionError
        async def failing_redis_operation():
            raise RedisConnectionError("Simulated Redis connection error")
        
        # Test that the circuit breaker opens after 3 failures
        for i in range(3):
            try:
                await redis_breaker.call_async(failing_redis_operation)
                assert False, "Expected RedisConnectionError to be raised"
            except RedisConnectionError:
                # Expected behavior - failure should be counted
                pass
        
        # Fourth call should fail-fast with CircuitBreakerError
        try:
            await redis_breaker.call_async(failing_redis_operation)
            assert False, "Expected CircuitBreakerError to be raised"
        except Exception as e:
            # Verify it's a CircuitBreakerError (aiobreaker specific)
            assert "CircuitBreakerError" in str(type(e)) or "open" in str(e).lower()
            
        # Verify state is OPEN
        assert redis_breaker.current_state.__class__.__name__ == "CircuitOpenState"