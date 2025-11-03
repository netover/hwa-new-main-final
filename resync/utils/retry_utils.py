"""
Utility functions for retrying asynchronous operations with backoff.

This module provides a simple implementation of an asynchronous retry
mechanism with exponential backoff and optional jitter.  It can be used
throughout the codebase to replace missing dependencies such as
``retry_with_backoff_async`` from external libraries.  The logic is
straightforward: it retries a coroutine a specified number of times
when certain exceptions are raised, waiting an exponentially increasing
amount of time between attempts.  If ``jitter`` is enabled, a random
component is added to the delay to avoid thundering herds.

Example usage::

    async def fetch_data():
        response = await client.get(url)
        response.raise_for_status()
        return response

    result = await retry_with_backoff_async(
        fetch_data,
        retries=3,
        base_delay=1.0,
        cap=10.0,
        jitter=True,
        retry_on=(httpx.RequestError, httpx.TimeoutException),
    )

The function returns the result of ``fetch_data`` or re-raises the
exception if all retries fail.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, Iterable, Tuple, Type


async def retry_with_backoff_async(
    func: Callable[[], Awaitable[Any]],
    retries: int = 3,
    base_delay: float = 1.0,
    cap: float = 10.0,
    jitter: bool = False,
    retry_on: Iterable[Type[Exception]] = (Exception,),
) -> Any:
    """Retry an asynchronous callable using exponential backoff.

    Args:
        func: A zero‑argument coroutine function to be executed.
        retries: The maximum number of retry attempts.  A value of ``0``
            means the function is executed once with no retries.
        base_delay: The initial delay between retries in seconds.
        cap: The maximum delay between retries in seconds.  Delays are
            doubled on each retry up to this cap.
        jitter: Whether to add randomness to the delay.  When enabled, the
            actual delay will be a random number between 0 and the
            calculated delay.
        retry_on: An iterable of exception types that trigger a retry.  Any
            exception not in this collection will be propagated immediately.

    Returns:
        The result returned by ``func`` if it eventually succeeds.

    Raises:
        Exception: The last exception raised by ``func`` if all retries
            fail.
    """
    exceptions: Tuple[Type[Exception], ...] = tuple(retry_on)
    attempt = 0
    while True:
        try:
            return await func()
        except exceptions as exc:
            attempt += 1
            if attempt > retries:
                # Exhausted retries; re-raise the last exception
                raise
            # Calculate delay with exponential backoff
            delay = min(cap, base_delay * (2 ** (attempt - 1)))
            if jitter:
                delay = random.uniform(0, delay)
            await asyncio.sleep(delay)
