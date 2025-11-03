"""
Circuit Breaker Implementation

This module provides a standalone circuit breaker utility for health checks
and service protection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Simple circuit breaker implementation for health checks."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self._last_check = datetime.now()

    async def call(self, func, *args, **kwargs):
        """Executes the function with circuit breaker protection."""
        if self.state == "open":
            # Check if it's time to attempt recovery
            if (
                datetime.now() - self.last_failure_time
            ).seconds > self.recovery_timeout:
                self.state = "half-open"
            else:
                # Circuit is open, fail fast
                raise RuntimeError(
                    f"Circuit breaker is open for {self.recovery_timeout}s"
                )

        try:
            result = await func(*args, **kwargs)
            # On success, reset if we were in half-open state
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            # If we've exceeded threshold, open the circuit
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    "circuit_breaker_opened", failure_count=self.failure_count
                )
            raise e

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": (
                self.last_failure_time.isoformat()
                if self.last_failure_time
                else None
            ),
        }


# Global adaptive circuit breaker instances
adaptive_tws_api_breaker = CircuitBreaker(
    failure_threshold=10, recovery_timeout=120
)

adaptive_llm_api_breaker = CircuitBreaker(
    failure_threshold=15, recovery_timeout=180
)




