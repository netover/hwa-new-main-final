"""
Testes para os algoritmos de rate limiting melhorados.
"""

import pytest
import asyncio
import time

from resync.core.rate_limiter_improved import (
    TokenBucketRateLimiter,
    LeakyBucketRateLimiter,
    SlidingWindowRateLimiter,
    RateLimiterManager,
)


class TestTokenBucketRateLimiter:
    """Testes para TokenBucketRateLimiter."""

    @pytest.fixture
    async def limiter(self):
        """Fixture para TokenBucket limiter."""
        limiter = TokenBucketRateLimiter(rate=10, capacity=20, name="test")
        yield limiter

    @pytest.mark.asyncio
    async def test_initial_state(self, limiter):
        """Testa estado inicial."""
        assert limiter.tokens == 20  # Capacidade máxima
        assert limiter.rate == 10
        assert limiter.capacity == 20

    @pytest.mark.asyncio
    async def test_acquire_within_capacity(self, limiter):
        """Testa aquisição dentro da capacidade."""
        assert await limiter.acquire(5) is True
        assert limiter.tokens == 15
        assert limiter.requests_allowed == 1
        assert limiter.requests_denied == 0

    @pytest.mark.asyncio
    async def test_acquire_exceeds_capacity(self, limiter):
        """Testa aquisição que excede capacidade."""
        # Consome todos os tokens
        assert await limiter.acquire(20) is True
        assert limiter.tokens == 0

        # Tenta adquirir mais
        assert await limiter.acquire(1) is False
        assert limiter.requests_denied == 1

    @pytest.mark.asyncio
    async def test_token_regeneration(self, limiter):
        """Testa regeneração de tokens ao longo do tempo."""
        # Consome todos os tokens
        assert await limiter.acquire(20) is True

        # Espera regeneração (1 segundo = 10 tokens)
        await asyncio.sleep(1.1)

        # Deve ter regenerado tokens
        assert await limiter.acquire(5) is True
        assert limiter.tokens <= 15  # 10 regenerados - 5 consumidos

    @pytest.mark.asyncio
    async def test_wait_and_acquire(self, limiter):
        """Testa wait_and_acquire."""
        # Consome todos os tokens
        assert await limiter.acquire(20) is True

        start_time = time.time()
        await limiter.wait_and_acquire(5)
        elapsed = time.time() - start_time

        # Deve ter esperado cerca de 0.5 segundos (5 tokens / 10 tokens/seg)
        assert elapsed >= 0.4
        assert elapsed <= 1.0

    @pytest.mark.asyncio
    async def test_stats(self, limiter):
        """Testa coleta de estatísticas."""
        await limiter.acquire(5)
        await limiter.acquire(25)  # Deve falhar

        stats = limiter.get_stats()
        assert stats["requests_allowed"] == 1
        assert stats["requests_denied"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["tokens_consumed"] == 5


class TestLeakyBucketRateLimiter:
    """Testes para LeakyBucketRateLimiter."""

    @pytest.fixture
    async def limiter(self):
        """Fixture para LeakyBucket limiter."""
        limiter = LeakyBucketRateLimiter(
            rate=2, capacity=5, name="test"
        )  # 2 vazamentos por segundo
        await limiter.start()
        yield limiter
        await limiter.stop()

    @pytest.mark.asyncio
    async def test_initial_state(self, limiter):
        """Testa estado inicial."""
        assert limiter.rate == 2
        assert limiter.capacity == 5
        assert len(limiter.queue) == 0

    @pytest.mark.asyncio
    async def test_acquire_within_capacity(self, limiter):
        """Testa aquisição dentro da capacidade."""
        for i in range(5):
            assert await limiter.acquire() is True

        assert len(limiter.queue) == 5
        assert limiter.requests_allowed == 5

    @pytest.mark.asyncio
    async def test_acquire_exceeds_capacity(self, limiter):
        """Testa aquisição que excede capacidade."""
        # Preenche o bucket
        for i in range(5):
            assert await limiter.acquire() is True

        # Próxima deve falhar
        assert await limiter.acquire() is False
        assert limiter.requests_denied == 1

    @pytest.mark.asyncio
    async def test_leakage(self, limiter):
        """Testa vazamento ao longo do tempo."""
        # Preenche o bucket
        for i in range(5):
            assert await limiter.acquire() is True

        # Espera vazamento (0.6 segundos = ~1.2 vazamentos)
        await asyncio.sleep(0.6)

        # Deve conseguir adicionar mais uma requisição
        assert await limiter.acquire() is True

    @pytest.mark.asyncio
    async def test_wait_and_acquire(self, limiter):
        """Testa wait_and_acquire."""
        # Preenche o bucket
        for i in range(5):
            assert await limiter.acquire() is True

        start_time = time.time()
        await limiter.wait_and_acquire()
        elapsed = time.time() - start_time

        # Deve ter esperado pelo vazamento (~0.5 segundos)
        assert elapsed >= 0.4

    @pytest.mark.asyncio
    async def test_stats(self, limiter):
        """Testa coleta de estatísticas."""
        for i in range(3):
            await limiter.acquire()

        await asyncio.sleep(1.1)  # Espera processamento

        stats = limiter.get_stats()
        assert stats["requests_allowed"] == 3
        assert stats["current_queue_size"] == 3
        assert stats["running"] is True


class TestSlidingWindowRateLimiter:
    """Testes para SlidingWindowRateLimiter."""

    @pytest.fixture
    async def limiter(self):
        """Fixture para SlidingWindow limiter."""
        return SlidingWindowRateLimiter(
            requests_per_window=3, window_seconds=1, name="test"
        )

    @pytest.mark.asyncio
    async def test_initial_state(self, limiter):
        """Testa estado inicial."""
        assert limiter.requests_per_window == 3
        assert limiter.window_seconds == 1
        assert len(limiter.requests) == 0

    @pytest.mark.asyncio
    async def test_acquire_within_window(self, limiter):
        """Testa aquisição dentro da janela."""
        for i in range(3):
            assert await limiter.acquire() is True

        assert len(limiter.requests) == 3
        assert limiter.requests_allowed == 3

    @pytest.mark.asyncio
    async def test_acquire_exceeds_window(self, limiter):
        """Testa aquisição que excede janela."""
        # Preenche a janela
        for i in range(3):
            assert await limiter.acquire() is True

        # Próxima deve falhar
        assert await limiter.acquire() is False
        assert limiter.requests_denied == 1

    @pytest.mark.asyncio
    async def test_window_sliding(self, limiter):
        """Testa deslizamento da janela."""
        # Preenche a janela
        for i in range(3):
            assert await limiter.acquire() is True

        # Espera a janela deslizar
        await asyncio.sleep(1.1)

        # Deve conseguir fazer novas requisições
        assert await limiter.acquire() is True
        assert limiter.requests_allowed == 4

    @pytest.mark.asyncio
    async def test_stats(self, limiter):
        """Testa coleta de estatísticas."""
        for i in range(2):
            await limiter.acquire()
        await limiter.acquire()  # Deve falhar

        stats = limiter.get_stats()
        assert stats["requests_allowed"] == 2
        assert stats["requests_denied"] == 1
        assert stats["success_rate"] == 2 / 3


class TestRateLimiterManager:
    """Testes para RateLimiterManager."""

    @pytest.fixture
    async def manager(self):
        """Fixture para manager."""
        manager = RateLimiterManager()
        yield manager
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_create_token_bucket(self, manager):
        """Testa criação de TokenBucket."""
        limiter = await manager.create_token_bucket("test_tb", 10, 20)
        assert limiter.name == "test_tb"
        assert limiter.rate == 10
        assert limiter.capacity == 20

        # Verifica registro no manager
        retrieved = manager.get_limiter("test_tb")
        assert retrieved is limiter

    @pytest.mark.asyncio
    async def test_create_leaky_bucket(self, manager):
        """Testa criação de LeakyBucket."""
        limiter = await manager.create_leaky_bucket("test_lb", 5, 10)
        assert limiter.name == "test_lb"
        assert limiter.rate == 5
        assert limiter.capacity == 10

    @pytest.mark.asyncio
    async def test_create_sliding_window(self, manager):
        """Testa criação de SlidingWindow."""
        limiter = await manager.create_sliding_window("test_sw", 5, 2.0)
        assert limiter.name == "test_sw"
        assert limiter.requests_per_window == 5
        assert limiter.window_seconds == 2.0

    @pytest.mark.asyncio
    async def test_duplicate_names(self, manager):
        """Testa prevenção de nomes duplicados."""
        await manager.create_token_bucket("duplicate", 10, 20)

        with pytest.raises(ValueError, match="already exists"):
            await manager.create_leaky_bucket("duplicate", 5, 10)

    @pytest.mark.asyncio
    async def test_remove_limiter(self, manager):
        """Testa remoção de limiter."""
        limiter = await manager.create_token_bucket("to_remove", 10, 20)
        assert manager.get_limiter("to_remove") is limiter

        result = await manager.remove_limiter("to_remove")
        assert result is True

        with pytest.raises(KeyError):
            manager.get_limiter("to_remove")

    @pytest.mark.asyncio
    async def test_get_all_stats(self, manager):
        """Testa obtenção de todas as estatísticas."""
        await manager.create_token_bucket("tb1", 10, 20)
        await manager.create_leaky_bucket("lb1", 5, 10)

        stats = manager.get_all_stats()
        assert "tb1" in stats
        assert "lb1" in stats
        assert stats["tb1"]["algorithm"] == "token_bucket"
        assert stats["lb1"]["algorithm"] == "leaky_bucket"
