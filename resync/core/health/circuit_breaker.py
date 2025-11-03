"""
Circuit Breaker Implementation

This module provides a circuit breaker pattern implementation for health checks
and external service calls. The circuit breaker prevents cascading failures by
temporarily stopping calls to failing services.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """
    Simple circuit breaker implementation for health checks.

    The circuit breaker has three states:
    - Closed: Normal operation, calls pass through
    - Open: Failure threshold exceeded, calls fail fast
    - Half-Open: Testing if service has recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str | None = None,
    ):
        """
        Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            name: Optional name for the circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name or "unnamed_circuit_breaker"

        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state: str = "closed"  # closed, open, half-open
        self._last_check = datetime.now()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute the function with circuit breaker protection.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            Exception: If circuit is open or function execution fails
        """
        if self.state == "open":
            # Check if it's time to attempt recovery
            if (
                self.last_failure_time
                and (datetime.now() - self.last_failure_time).seconds
                > self.recovery_timeout
            ):
                self.state = "half-open"
                logger.debug(
                    "circuit_breaker_half_open",
                    circuit_breaker=self.name,
                    failure_count=self.failure_count,
                )
            else:
                # Circuit is open, fail fast
                raise Exception(
                    f"Circuit breaker '{self.name}' is open for {self.recovery_timeout}s"
                )

        try:
            result = await func(*args, **kwargs)
            # On success, reset if we were in half-open state
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
                logger.info(
                    "circuit_breaker_closed",
                    circuit_breaker=self.name,
                    previous_failures=self.failure_count,
                )
            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            # If we've exceeded threshold, open the circuit
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    "circuit_breaker_opened",
                    circuit_breaker=self.name,
                    failure_count=self.failure_count,
                )

            logger.error(
                "circuit_breaker_call_failed",
                circuit_breaker=self.name,
                failure_count=self.failure_count,
                error=str(e),
            )
            raise e

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.

        Returns:
            Dictionary with circuit breaker statistics
        """
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": (
                self.last_failure_time.isoformat()
                if self.last_failure_time
                else None
            ),
            "last_check": self._last_check.isoformat(),
        }

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        self._last_check = datetime.now()
        logger.info("circuit_breaker_reset", circuit_breaker=self.name)




