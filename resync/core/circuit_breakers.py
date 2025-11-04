"""Preconfigured circuit breakers used in tests."""

from __future__ import annotations

from datetime import timedelta

from aiobreaker import CircuitBreaker
from resync.utils.exceptions import AuthenticationError


def redis_breaker_listener(*args, **kwargs):
    return None


def tws_breaker_listener(*args, **kwargs):
    return None


def llm_breaker_listener(*args, **kwargs):
    return None


redis_breaker = CircuitBreaker(
    fail_max=3,
    timeout_duration=timedelta(seconds=30),
    exclude=[ValueError, TypeError],
    name="redis_operations",
    listeners=[redis_breaker_listener],
)

tws_breaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=timedelta(seconds=60),
    exclude=[AuthenticationError],
    name="tws_operations",
    listeners=[tws_breaker_listener],
)

llm_breaker = CircuitBreaker(
    fail_max=2,
    timeout_duration=timedelta(seconds=45),
    exclude=[],
    name="llm_operations",
    listeners=[llm_breaker_listener],
)


__all__ = ["redis_breaker", "tws_breaker", "llm_breaker"]
