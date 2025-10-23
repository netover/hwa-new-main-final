"""
Redis connection pool implementation for the Resync project.
Separated to follow Single Responsibility Principle.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

# Soft import for redis (optional dependency)
try:
    import redis.asyncio as redis
    from redis.asyncio import Redis as AsyncRedis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import RedisError
except ImportError:
    redis = None
    AsyncRedis = None
    RedisConnectionError = None
    RedisError = None

from resync.core.redis_init import is_redis_available, get_redis_client
import os
import logging

logger = logging.getLogger(__name__)


class RedisPool:
    def __init__(self, url: str | None = None):
        self._url = url
        self._client = None

    @property
    def client(self):
        if os.getenv("RESYNC_DISABLE_REDIS") == "1":
            raise RuntimeError("Redis disabled by RESYNC_DISABLE_REDIS=1")
        if not is_redis_available():
            raise RuntimeError("redis-py not installed")
        if self._client is None:
            if self._url:
                # usa URL explícita
                import redis.asyncio as redis  # type: ignore
                self._client = redis.from_url(self._url, encoding="utf-8", decode_responses=True)
                logger.info("Initialized Redis client from explicit URL (lazy).")
            else:
                # usa factory centralizada
                self._client = get_redis_client()
        return self._client
