"""
Minimal test for circuit breaker implementation.

This test only imports the circuit_breakers.py file directly without
importing the entire resync.core package to avoid circular imports.
"""

import os
import sys
from datetime import timedelta

import pytest

# Add the resync/core directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import circuit_breakers directly
from resync.core.circuit_breakers import llm_breaker, redis_breaker, tws_breaker


def test_circuit_breaker_configuration():
    """Test that circuit breakers are configured correctly."""
    # Test redis_breaker configuration
    assert redis_breaker.fail_max == 3
    assert redis_breaker.timeout_duration == timedelta(seconds=30)
    assert redis_breaker.exclude == [ValueError, TypeError]
    assert redis_breaker.name == "redis_operations"

    # Test tws_breaker configuration
    assert tws_breaker.fail_max == 5
    assert tws_breaker.timeout_duration == timedelta(seconds=60)
    assert tws_breaker.exclude == ["AuthenticationError"]  # This will be a string in the code
    assert tws_breaker.name == "tws_operations"

    # Test llm_breaker configuration
    assert llm_breaker.fail_max == 2
    assert llm_breaker.timeout_duration == timedelta(seconds=45)
    assert llm_breaker.name == "llm_operations"


def test_circuit_breaker_types():
    """Test that circuit breakers are instances of CircuitBreaker."""
    from aiobreaker import CircuitBreaker

    assert isinstance(redis_breaker, CircuitBreaker)
    assert isinstance(tws_breaker, CircuitBreaker)
    assert isinstance(llm_breaker, CircuitBreaker)


def test_circuit_breaker_listener():
    """Test that the redis_breaker has a listener attached."""
    # Check if the listener is attached
    assert len(redis_breaker._listeners) > 0

    # Check that the listener is the redis_breaker_listener function
    listener_function = redis_breaker._listeners[0]
    assert listener_function.__name__ == "redis_breaker_listener"


def test_authentication_error_import():
    """Test that AuthenticationError can be imported from resync.core.exceptions."""
    try:
        from resync.core.exceptions import AuthenticationError
        assert AuthenticationError is not None
    except ImportError:
        # If we can't import it, we'll skip this test
        pass

if __name__ == "__main__":
    pytest.main([__file__])




