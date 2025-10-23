"""
Gerenciador principal de idempotency refatorado.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from resync.core.idempotency.config import config
from resync.core.idempotency.exceptions import IdempotencyError, IdempotencyStorageError
from resync.core.idempotency.models import IdempotencyRecord
from resync.core.idempotency.storage import IdempotencyStorage
from resync.core.idempotency.validation import IdempotencyKeyValidator
from resync.core.idempotency.metrics import IdempotencyMetrics
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class IdempotencyManager:
    """
    Gerenciador de chaves de idempotência refatorado
    
    Responsável por armazenar e recuperar respostas de operações
    idempotentes, garantindo que operações críticas não sejam
    executadas múltiplas vezes.
    """

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.storage = IdempotencyStorage(redis_client)
        self.metrics = IdempotencyMetrics()

        logger.info(
            "Idempotency manager initialized",
            ttl_hours=config.ttl_hours,
            redis_db=config.redis_db,
            max_response_size_kb=config.max_response_size_kb,
        )

    async def get_cached_response(
        self, idempotency_key: str, request_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recupera resposta em cache para chave de idempotência

        Args:
            idempotency_key: Chave de idempotência
            request_data: Dados da requisição para validação (opcional)

        Returns:
            Resposta em cache ou None se não encontrada
        """
        self.metrics.total_requests += 1

        try:
            # Validar chave
            IdempotencyKeyValidator.validate(idempotency_key)
            
            key = self._make_key(idempotency_key)
            cached_record = await self.storage.get(key)
            
            if not cached_record:
                self.metrics.cache_misses += 1
                return None

            # Verificar se expirou (defesa extra)
            if self._is_expired(cached_record):
                await self.storage.delete(key)
                self.metrics.expired_cleanups += 1
                logger.warning(
                    "Expired idempotency record cleaned up",
                    idempotency_key=idempotency_key,
                )
                return None

            # Validar hash da requisição se fornecido
            if request_data is not None:
                current_hash = self._hash_request_data(request_data)
                if current_hash != cached_record.request_hash:
                    logger.warning(
                        "Idempotency key collision detected",
                        idempotency_key=idempotency_key,
                        stored_hash=cached_record.request_hash,
                        current_hash=current_hash,
                    )
                    # Em caso de colisão, não usar cache
                    return None

            self.metrics.cache_hits += 1

            logger.debug(
                "Idempotency cache hit",
                idempotency_key=idempotency_key,
                age_seconds=(self._now() - cached_record.created_at).total_seconds(),
            )

            return {
                "status_code": cached_record.status_code,
                "data": cached_record.response_data,
                "cached_at": cached_record.created_at.isoformat(),
                "expires_at": cached_record.expires_at.isoformat(),
            }

        except IdempotencyKeyError as e:
            logger.warning(
                "Invalid idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return None
        except IdempotencyStorageError as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Failed to get cached response",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return None
        except Exception as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Unexpected error getting cached response",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return None

    async def cache_response(
        self,
        idempotency_key: str,
        response_data: Dict[str, Any],
        status_code: int = 200,
        request_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Armazena resposta para chave de idempotência

        Args:
            idempotency_key: Chave de idempotência
            response_data: Dados da resposta
            status_code: Código de status HTTP
            request_data: Dados da requisição para hash
            metadata: Metadados adicionais

        Returns:
            True se armazenado com sucesso, False caso contrário
        """
        try:
            # Validar chave
            IdempotencyKeyValidator.validate(idempotency_key)
            
            # Verificar tamanho da resposta
            response_size = len(str(response_data).encode("utf-8"))
            max_size_bytes = config.max_response_size_kb * 1024

            if response_size > max_size_bytes:
                logger.warning(
                    "Response too large for idempotency cache",
                    idempotency_key=idempotency_key,
                    size_kb=response_size / 1024,
                    max_size_kb=config.max_response_size_kb,
                )
                return False

            # Criar registro
            now = self._now()
            expires_at = now + timedelta(hours=config.ttl_hours)

            record = IdempotencyRecord(
                idempotency_key=idempotency_key,
                request_hash=(
                    self._hash_request_data(request_data) if request_data else ""
                ),
                response_data=response_data,
                status_code=status_code,
                created_at=now,
                expires_at=expires_at,
                request_metadata=metadata or {},
            )

            # Armazenar
            key = self._make_key(idempotency_key)
            ttl_seconds = int((expires_at - now).total_seconds())
            success = await self.storage.set(key, record, ttl_seconds)

            if success:
                logger.debug(
                    "Response cached for idempotency",
                    idempotency_key=idempotency_key,
                    ttl_seconds=ttl_seconds,
                    size_kb=response_size / 1024,
                )
                return True
            else:
                logger.error(
                    "Failed to cache response", idempotency_key=idempotency_key
                )
                return False

        except IdempotencyKeyError as e:
            logger.warning(
                "Invalid idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except IdempotencyStorageError as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Failed to cache response",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except Exception as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Unexpected error caching response",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False

    async def is_processing(self, idempotency_key: str) -> bool:
        """
        Verifica se operação já está em processamento

        Args:
            idempotency_key: Chave de idempotência

        Returns:
            True se já está em processamento
        """
        try:
            IdempotencyKeyValidator.validate(idempotency_key)
            processing_key = self._make_processing_key(idempotency_key)
            return await self.storage.exists(processing_key)
        except IdempotencyKeyError as e:
            logger.warning(
                "Invalid idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except IdempotencyStorageError as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Failed to check processing status",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except Exception as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Unexpected error checking processing status",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False

    async def mark_processing(
        self, idempotency_key: str, ttl_seconds: int = 300
    ) -> bool:
        """
        Marca operação como em processamento

        Args:
            idempotency_key: Chave de idempotência
            ttl_seconds: TTL para a marca de processamento

        Returns:
            True se marcado com sucesso
        """
        try:
            IdempotencyKeyValidator.validate(idempotency_key)
            processing_key = self._make_processing_key(idempotency_key)
            data = {
                "started_at": self._now().isoformat(),
                "ttl_seconds": ttl_seconds,
            }
            success = await self.storage.set(processing_key, IdempotencyRecord(
                idempotency_key=idempotency_key,
                request_hash="",
                response_data=data,
                status_code=200,
                created_at=self._now(),
                expires_at=self._now() + timedelta(seconds=ttl_seconds),
            ), ttl_seconds)
            
            if success:
                logger.debug(
                    "Operation marked as processing",
                    idempotency_key=idempotency_key,
                    ttl_seconds=ttl_seconds,
                )
                return True
            else:
                logger.error(
                    "Failed to mark operation as processing",
                    idempotency_key=idempotency_key,
                )
                return False

        except IdempotencyKeyError as e:
            logger.warning(
                "Invalid idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except IdempotencyStorageError as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Failed to mark processing",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except Exception as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Unexpected error marking processing",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False

    async def clear_processing(self, idempotency_key: str) -> bool:
        """
        Remove marca de processamento

        Args:
            idempotency_key: Chave de idempotência

        Returns:
            True se removido com sucesso
        """
        try:
            IdempotencyKeyValidator.validate(idempotency_key)
            processing_key = self._make_processing_key(idempotency_key)
            deleted = await self.storage.delete(processing_key)

            if deleted:
                logger.debug("Processing mark cleared", idempotency_key=idempotency_key)
            else:
                logger.debug(
                    "No processing mark to clear", idempotency_key=idempotency_key
                )

            return True

        except IdempotencyKeyError as e:
            logger.warning(
                "Invalid idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except IdempotencyStorageError as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Failed to clear processing mark",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except Exception as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Unexpected error clearing processing mark",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False

    async def invalidate_key(self, idempotency_key: str) -> bool:
        """
        Invalida chave de idempotência (remove do cache)

        Args:
            idempotency_key: Chave a ser invalidada

        Returns:
            True se invalidada com sucesso
        """
        try:
            IdempotencyKeyValidator.validate(idempotency_key)
            key = self._make_key(idempotency_key)
            processing_key = self._make_processing_key(idempotency_key)

            # Remover ambos: resposta cacheada e marca de processamento
            deleted_count = await self.storage.delete(key)
            deleted_processing = await self.storage.delete(processing_key)

            logger.info(
                "Idempotency key invalidated",
                idempotency_key=idempotency_key,
                keys_deleted=deleted_count + (1 if deleted_processing else 0),
            )

            return deleted_count > 0 or deleted_processing

        except IdempotencyKeyError as e:
            logger.warning(
                "Invalid idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except IdempotencyStorageError as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Failed to invalidate idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False
        except Exception as e:
            self.metrics.storage_errors += 1
            logger.error(
                "Unexpected error invalidating idempotency key",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas atuais"""
        return {
            "total_requests": self.metrics.total_requests,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "hit_rate": self.metrics.hit_rate,
            "concurrent_blocks": self.metrics.concurrent_blocks,
            "storage_errors": self.metrics.storage_errors,
            "expired_cleanups": self.metrics.expired_cleanups,
        }

    def _make_key(self, idempotency_key: str) -> str:
        """Cria chave Redis para resposta cacheada"""
        return f"{config.key_prefix}:{idempotency_key}"

    def _make_processing_key(self, idempotency_key: str) -> str:
        """Cria chave Redis para marca de processamento"""
        return f"{config.processing_prefix}:{idempotency_key}"

    def _hash_request_data(self, request_data: Dict[str, Any]) -> str:
        """
        Gera hash dos dados da requisição para detectar mudanças

        Args:
            request_data: Dados da requisição

        Returns:
            Hash SHA256 dos dados
        """
        # Normalizar dados para hash consistente
        import json
        normalized = json.dumps(request_data, sort_keys=True)
        import hashlib
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _now(self) -> datetime:
        """Obtém data/hora atual"""
        from datetime import datetime
        return datetime.utcnow()

    def _is_expired(self, record: IdempotencyRecord) -> bool:
        """Verifica se registro expirou"""
        return self._now() > record.expires_at
