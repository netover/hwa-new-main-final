"""
Testes unitários para o sistema de Idempotency Keys do Resync

Testa IdempotencyManager, middleware e funcionalidades relacionadas.

Author: Resync Team
Date: October 2025
"""

import json
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis

from resync.api.middleware.idempotency import IdempotencyMiddleware
from resync.core.idempotency import (
    IdempotencyConfig,
    IdempotencyManager,
    IdempotencyRecord,
    generate_idempotency_key,
    validate_idempotency_key,
)


class TestIdempotencyManager:
    """Testes para IdempotencyManager"""

    @pytest.fixture
    async def redis_mock(self):
        """Mock Redis para testes"""
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock()
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.exists = AsyncMock()
        return redis

    @pytest.fixture
    def config(self):
        return IdempotencyConfig(
            ttl_hours=1,  # TTL curto para testes
            key_prefix="test:idempotency",
            processing_prefix="test:processing",
        )

    @pytest.fixture
    def manager(self, redis_mock, config):
        return IdempotencyManager(redis_mock, config)

    @pytest.mark.asyncio
    async def test_get_cached_response_hit(self, manager, redis_mock):
        """Testa hit no cache de idempotency"""

        # Mock resposta cacheada
        cached_record = IdempotencyRecord(
            idempotency_key="test-key",
            request_hash="hash123",
            response_data={"result": "cached"},
            status_code=200,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        redis_mock.get.return_value = json.dumps(cached_record.to_dict())

        result = await manager.get_cached_response("test-key")

        assert result is not None
        assert result["status_code"] == 200
        assert result["data"] == {"result": "cached"}
        assert "cached_at" in result
        assert "expires_at" in result

        redis_mock.get.assert_called_once_with("test:idempotency:test-key")

    @pytest.mark.asyncio
    async def test_get_cached_response_miss(self, manager, redis_mock):
        """Testa miss no cache de idempotency"""

        redis_mock.get.return_value = None

        result = await manager.get_cached_response("test-key")

        assert result is None
        redis_mock.get.assert_called_once_with("test:idempotency:test-key")

    @pytest.mark.asyncio
    async def test_get_cached_response_expired(self, manager, redis_mock):
        """Testa resposta expirada"""

        # Mock resposta expirada
        expired_record = IdempotencyRecord(
            idempotency_key="test-key",
            request_hash="hash123",
            response_data={"result": "expired"},
            status_code=200,
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )

        redis_mock.get.return_value = json.dumps(expired_record.to_dict())
        redis_mock.delete = AsyncMock()

        result = await manager.get_cached_response("test-key")

        assert result is None
        redis_mock.delete.assert_called_once_with("test:idempotency:test-key")

    @pytest.mark.asyncio
    async def test_cache_response_success(self, manager, redis_mock):
        """Testa armazenamento bem-sucedido de resposta"""

        redis_mock.setex.return_value = True

        success = await manager.cache_response(
            idempotency_key="test-key",
            response_data={"result": "success"},
            status_code=201,
        )

        assert success is True
        redis_mock.setex.assert_called_once()

        # Verificar argumentos
        call_args = redis_mock.setex.call_args
        key, ttl, data = call_args[0]

        assert key == "test:idempotency:test-key"
        assert isinstance(ttl, int)
        assert ttl > 0

        # Verificar dados serializados
        record_data = json.loads(data)
        record = IdempotencyRecord.from_dict(record_data)

        assert record.idempotency_key == "test-key"
        assert record.response_data == {"result": "success"}
        assert record.status_code == 201

    @pytest.mark.asyncio
    async def test_cache_response_too_large(self, manager, redis_mock):
        """Testa rejeição de resposta muito grande"""

        large_data = {"data": "x" * (65 * 1024)}  # Maior que 64KB

        success = await manager.cache_response(
            idempotency_key="test-key", response_data=large_data, status_code=200
        )

        assert success is False
        redis_mock.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_processing_true(self, manager, redis_mock):
        """Testa verificação de processamento em andamento"""

        redis_mock.exists.return_value = True

        is_processing = await manager.is_processing("test-key")

        assert is_processing is True
        redis_mock.exists.assert_called_once_with("test:processing:test-key")

    @pytest.mark.asyncio
    async def test_mark_processing_success(self, manager, redis_mock):
        """Testa marcação de processamento"""

        redis_mock.setex.return_value = True

        success = await manager.mark_processing("test-key", ttl_seconds=60)

        assert success is True
        redis_mock.setex.assert_called_once()

        # Verificar argumentos da chamada
        call_args = redis_mock.setex.call_args
        key, ttl, data = call_args[0]

        assert key == "test:processing:test-key"
        assert ttl == 60

        # Verificar que os dados são um JSON válido com a estrutura esperada
        parsed_data = json.loads(data)
        assert "started_at" in parsed_data
        assert parsed_data["ttl_seconds"] == 60

    @pytest.mark.asyncio
    async def test_clear_processing_success(self, manager, redis_mock):
        """Testa limpeza de marca de processamento"""

        redis_mock.delete.return_value = 1

        success = await manager.clear_processing("test-key")

        assert success is True
        redis_mock.delete.assert_called_once_with("test:processing:test-key")

    @pytest.mark.asyncio
    async def test_invalidate_key(self, manager, redis_mock):
        """Testa invalidação de chave"""

        redis_mock.delete.return_value = 2  # Duas chaves deletadas

        success = await manager.invalidate_key("test-key")

        assert success is True
        redis_mock.delete.assert_called_once_with(
            "test:idempotency:test-key", "test:processing:test-key"
        )

    def test_get_metrics(self, manager):
        """Testa obtenção de métricas"""

        metrics = manager.get_metrics()

        expected_keys = [
            "total_requests",
            "cache_hits",
            "cache_misses",
            "hit_rate",
            "concurrent_blocks",
            "storage_errors",
            "expired_cleanups",
        ]

        for key in expected_keys:
            assert key in metrics
            assert isinstance(metrics[key], (int, float))


class TestIdempotencyRecord:
    """Testes para IdempotencyRecord"""

    def test_to_dict_from_dict(self):
        """Testa serialização e desserialização"""

        original = IdempotencyRecord(
            idempotency_key="test-key",
            request_hash="hash123",
            response_data={"result": "test"},
            status_code=200,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            request_metadata={"user_id": "123"},
        )

        # Serializar
        data = original.to_dict()

        # Desserializar
        restored = IdempotencyRecord.from_dict(data)

        # Verificar igualdade
        assert restored.idempotency_key == original.idempotency_key
        assert restored.request_hash == original.request_hash
        assert restored.response_data == original.response_data
        assert restored.status_code == original.status_code
        assert restored.request_metadata == original.request_metadata

        # Verificar timestamps (aproximadamente)
        time_diff_created = abs(
            (restored.created_at - original.created_at).total_seconds()
        )
        time_diff_expires = abs(
            (restored.expires_at - original.expires_at).total_seconds()
        )

        assert time_diff_created < 1  # Menos de 1 segundo de diferença
        assert time_diff_expires < 1


class TestIdempotencyMiddleware:
    """Testes para IdempotencyMiddleware"""

    @pytest.fixture
    def manager_mock(self):
        """Mock IdempotencyManager"""
        manager = AsyncMock()
        manager.get_cached_response = AsyncMock()
        manager.cache_response = AsyncMock()
        manager.is_processing = AsyncMock()
        manager.mark_processing = AsyncMock()
        manager.clear_processing = AsyncMock()
        return manager

    @pytest.fixture
    def middleware(self, manager_mock):
        """Middleware configurado"""
        return IdempotencyMiddleware(
            app=None,
            idempotency_manager=manager_mock,
            idempotency_header="X-Idempotency-Key",
        )

    @pytest.mark.asyncio
    async def test_dispatch_with_cached_response(self, middleware, manager_mock):
        """Testa dispatch com resposta cacheada"""

        # Mock resposta cacheada
        cached_response = {
            "status_code": 200,
            "data": {"result": "cached"},
            "cached_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }
        manager_mock.get_cached_response.return_value = cached_response

        # Criar request mock
        request = MagicMock(spec=["method", "url", "headers"])
        request.method = "POST"
        request.url.path = "/api/test"
        request.headers = {"X-Idempotency-Key": "test-key"}

        # Criar call_next mock
        call_next = AsyncMock()

        # Executar middleware
        response = await middleware.dispatch(request, call_next)

        # Verificar que call_next não foi chamado
        call_next.assert_not_called()

        # Verificar que resposta cacheada foi retornada
        assert response.status_code == 200
        assert response.headers.get("X-Idempotency-Cache") == "HIT"

        manager_mock.get_cached_response.assert_called_once_with("test-key", ANY)

    @pytest.mark.asyncio
    async def test_dispatch_operation_in_progress(self, middleware, manager_mock):
        """Testa dispatch quando operação está em progresso"""

        # Configurar mocks
        manager_mock.get_cached_response.return_value = None
        manager_mock.is_processing.return_value = True

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/test"
        request.headers = {"X-Idempotency-Key": "test-key"}

        call_next = AsyncMock()

        # Executar middleware - deve lançar 409
        with pytest.raises(Exception) as exc_info:
            await middleware.dispatch(request, call_next)

        assert exc_info.value.status_code == 409
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_successful_operation(self, middleware, manager_mock):
        """Testa dispatch de operação bem-sucedida"""

        # Configurar mocks
        manager_mock.get_cached_response.return_value = None
        manager_mock.is_processing.return_value = False
        manager_mock.mark_processing.return_value = True
        manager_mock.cache_response.return_value = True

        # Mock response da operação
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.body = json.dumps({"id": "123"}).encode()

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/test"
        request.headers = {"X-Idempotency-Key": "test-key"}

        call_next = AsyncMock(return_value=mock_response)

        # Executar middleware
        await middleware.dispatch(request, call_next)

        # Verificar que operação foi executada
        call_next.assert_called_once()

        # Verificar que resposta foi cacheada
        manager_mock.cache_response.assert_called_once()

        # Verificar que processamento foi limpo
        manager_mock.clear_processing.assert_called_once_with("test-key")

    @pytest.mark.asyncio
    async def test_dispatch_excludes_get_requests(self, middleware, manager_mock):
        """Testa que GET requests são excluídas"""

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/test"
        request.headers = {}

        call_next = AsyncMock(return_value=MagicMock())

        # Executar middleware
        await middleware.dispatch(request, call_next)

        # Verificar que idempotency não foi aplicada
        call_next.assert_called_once()
        manager_mock.get_cached_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_requires_idempotency_key_for_post(
        self, middleware, manager_mock
    ):
        """Testa que POST requer idempotency key"""

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/test"
        request.headers = {}  # Sem idempotency key

        call_next = AsyncMock()

        # Executar middleware - deve lançar 400
        with pytest.raises(Exception) as exc_info:
            await middleware.dispatch(request, call_next)

        assert exc_info.value.status_code == 400
        call_next.assert_not_called()


class TestUtilityFunctions:
    """Testes para funções utilitárias"""

    def test_generate_idempotency_key(self):
        """Testa geração de chave de idempotency"""

        key1 = generate_idempotency_key()
        key2 = generate_idempotency_key()

        # Verificar formato UUID
        assert validate_idempotency_key(key1)
        assert validate_idempotency_key(key2)

        # Verificar unicidade
        assert key1 != key2

    def test_validate_idempotency_key_valid(self):
        """Testa validação de chave válida"""

        import uuid

        valid_key = str(uuid.uuid4())

        assert validate_idempotency_key(valid_key)

    def test_validate_idempotency_key_invalid(self):
        """Testa validação de chave inválida"""

        invalid_keys = [
            "not-a-uuid",
            "12345678-1234-1234-1234-1234567890123",  # Muito longo
            "12345678-1234-1234-1234-12345678901",  # Muito curto
            "12345678-1234-1234-g234-123456789012",  # Caractere inválido
        ]

        for invalid_key in invalid_keys:
            assert not validate_idempotency_key(invalid_key)


class TestMiddlewareIntegration:
    """Testes de integração do middleware"""

    @pytest.mark.asyncio
    async def test_middleware_with_real_manager(self):
        """Testa middleware com IdempotencyManager real (usando mock Redis)"""

        # Criar Redis mock
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.exists = AsyncMock(return_value=False)
        redis_mock.delete = AsyncMock(return_value=1)

        # Criar manager
        config = IdempotencyConfig(ttl_hours=1)
        manager = IdempotencyManager(redis_mock, config)

        # Criar middleware
        middleware = IdempotencyMiddleware(
            app=None,
            idempotency_manager=manager,
            idempotency_header="X-Idempotency-Key",
        )

        # Criar request
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/test"
        request.headers = {"X-Idempotency-Key": "550e8400-e29b-41d4-a716-446655440000"}

        # Criar response mock
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.body = json.dumps({"id": "123"}).encode()

        call_next = AsyncMock(return_value=mock_response)

        # Executar
        response = await middleware.dispatch(request, call_next)

        # Verificar que operação foi executada
        call_next.assert_called_once()
        assert response == mock_response

        # Verificar que resposta foi cacheada
        redis_mock.setex.assert_called()


# Fixtures compartilhados


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reseta mocks entre testes"""
    yield


@pytest.fixture
def event_loop():
    """Event loop para testes assíncronos"""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
