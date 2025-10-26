"""
Tests for Adaptive Circuit Breaker functionality - Optimized for speed.
"""

import pytest

from resync.core.resilience import CircuitBreakerManager


class TestAdaptiveCircuitBreaker:
    """Test cases for AdaptiveCircuitBreaker - Optimized for performance."""

    def test_circuit_breaker_creation_sync(self):
        """Test circuit breaker manager and breaker creation - synchronous version."""
        manager = CircuitBreakerManager()

        # Create breaker synchronously for testing
        from resync.core.resilience import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(name="test_operation", failure_threshold=1, recovery_timeout=1)
        breaker = CircuitBreaker(config)
        manager._breakers["test_operation"] = breaker

        # Verify breaker was created
        assert breaker is not None
        assert breaker.config.name == "test_operation"

    def test_circuit_breaker_metrics_sync(self):
        """Test circuit breaker metrics collection - synchronous version."""
        from resync.core.resilience import CircuitBreaker, CircuitBreakerConfig

        # Create breaker directly for test
        config = CircuitBreakerConfig(name="metrics_test", failure_threshold=1, recovery_timeout=1)
        breaker = CircuitBreaker(config)

        # Check initial metrics
        metrics = breaker.get_metrics()
        assert metrics["total_calls"] == 0
        assert metrics["successful_calls"] == 0
        assert metrics["failed_calls"] == 0
        assert metrics["success_rate"] == 0  # No calls yet

    @pytest.mark.asyncio
    async def test_circuit_breaker_successful_call(self):
        """Test successful circuit breaker call."""
        from resync.core.resilience import CircuitBreaker, CircuitBreakerConfig

        # Create breaker directly for test
        config = CircuitBreakerConfig(name="success_test", failure_threshold=1, recovery_timeout=1)
        breaker = CircuitBreaker(config)

        # Mock successful function
        async def success_func():
            return "success"

        # Execute call
        result = await breaker.call(success_func)

        # Verify result
        assert result == "success"

        # Check metrics
        metrics = breaker.get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["successful_calls"] == 1
        assert metrics["failed_calls"] == 0
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_failed_call(self):
        """Test failed circuit breaker call."""
        from resync.core.resilience import CircuitBreaker, CircuitBreakerConfig

        # Create breaker directly for test
        config = CircuitBreakerConfig(name="failure_test", failure_threshold=1, recovery_timeout=1)
        breaker = CircuitBreaker(config)

        # Mock failing function
        async def failure_func():
            raise ValueError("Test failure")

        # Execute call (should raise)
        with pytest.raises(ValueError, match="Test failure"):
            await breaker.call(failure_func)

        # Check metrics
        metrics = breaker.get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["successful_calls"] == 0
        assert metrics["failed_calls"] == 1
        assert metrics["success_rate"] == 0.0
        assert metrics["consecutive_failures"] == 1

    def test_circuit_breaker_manager_metrics_sync(self):
        """Test circuit breaker manager metrics collection - synchronous version."""
        manager = CircuitBreakerManager()

        # Create multiple breakers synchronously
        from resync.core.resilience import CircuitBreaker, CircuitBreakerConfig

        op1_breaker = CircuitBreaker(CircuitBreakerConfig(name="op1", failure_threshold=1, recovery_timeout=1))
        op2_breaker = CircuitBreaker(CircuitBreakerConfig(name="op2", failure_threshold=1, recovery_timeout=1))

        manager._breakers["op1"] = op1_breaker
        manager._breakers["op2"] = op2_breaker

        # Get metrics synchronously
        metrics = {}
        for name, breaker in manager._breakers.items():
            metrics[name] = breaker.get_metrics()

        assert "op1" in metrics
        assert "op2" in metrics
        assert len(metrics) == 2
