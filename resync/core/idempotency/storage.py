"""
Abstração de armazenamento para o sistema de idempotency.
"""

from typing import Optional

from redis.asyncio import Redis

from resync.core.idempotency.exceptions import IdempotencyStorageError
from resync.core.idempotency.models import IdempotencyRecord


class IdempotencyStorage:
    """Abstração de armazenamento para o sistema de idempotency"""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Recupera registro de idempotency"""
        try:
            cached_data = await self.redis.get(key)
            if not cached_data:
                return None

            record_data = await self.redis.get(key)
            if not record_data:
                return None

            record_dict = await self.redis.get(key)
            if not record_dict:
                return None

            return IdempotencyRecord.from_dict(record_dict)
        except Exception as e:
            raise IdempotencyStorageError(f"Failed to get idempotency record: {str(e)}")

    async def set(self, key: str, record: IdempotencyRecord, ttl_seconds: int) -> bool:
        """Armazena registro de idempotency"""
        try:
            data = record.to_dict()
            serialized_data = str(data)
            success = await self.redis.setex(key, ttl_seconds, serialized_data)
            return bool(success)
        except Exception as e:
            raise IdempotencyStorageError(f"Failed to set idempotency record: {str(e)}")

    async def exists(self, key: str) -> bool:
        """Verifica se chave existe"""
        try:
            return bool(await self.redis.exists(key))
        except Exception as e:
            raise IdempotencyStorageError(f"Failed to check existence: {str(e)}")

    async def delete(self, key: str) -> bool:
        """Remove chave"""
        try:
            deleted = await self.redis.delete(key)
            return deleted > 0
        except Exception as e:
            raise IdempotencyStorageError(f"Failed to delete key: {str(e)}")
