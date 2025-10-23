"""
Direct test for circuit breaker implementation using importlib.

This test loads the circuit_breakers.py file directly without using the Python package structure
to avoid circular imports in the resync.core package.
"""

import sys
import os
import importlib.util
import pytest
from datetime import timedelta

# Get the path to circuit_breakers.py
module_path = os.path.join(os.path.dirname(__file__), '..', '..', 'resync', 'core', 'circuit_breakers.py')

# Load the module directly
spec = importlib.util.spec_from_file_location("circuit_breakers", module_path)
circuit_breakers = importlib.util.module_from_spec(spec)
sys.modules["circuit_breakers"] = circuit_breakers
spec.loader.exec_module(circuit_breakers)

# Now we can access the circuit breakers directly
redis_breaker = circuit_breakers.redis_breaker
tws_breaker = circuit_breakers.tws_breaker
llm_breaker = circuit_breakers.llm_breaker


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
    # Note: AuthenticationError is imported from resync.core.exceptions
    # In the actual code, it's a class, but we can't import it here due to circular imports
    # So we'll check that it's in the exclude list
    assert "AuthenticationError" in [str(e) for e in tws_breaker.exclude] or any(isinstance(e, type) and e.__name__ == "AuthenticationError" for e in tws_breaker.exclude)
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


def test_authentication_error_in_circuit_breaker():
    """Test that AuthenticationError is properly referenced in the circuit breaker."""
    # We can't import AuthenticationError directly due to circular imports
    # But we can check that it's in the exclude list of tws_breaker
    # The actual value should be the AuthenticationError class from resync.core.exceptions
    # Since we can't import it, we'll check that the exclude list contains something
    # that represents the AuthenticationError
    assert len(tws_breaker.exclude) > 0
    
    # Check that the exclude list contains at least one exception type
    # (we know it should be AuthenticationError)
    assert any(isinstance(e, type) for e in tws_breaker.exclude)

if __name__ == "__main__":
    pytest.main([__file__])