"""
Testes para o TWS Client Factory.
"""

from unittest.mock import MagicMock

import pytest

from resync.services.tws_client_factory import (
    ProductionTWSClient,
    TestTWSClient,
    TWSClientFactory,
    TWSConfig,
)


class TestTWSConfig:
    """Testes para TWSConfig."""

    def test_valid_config(self):
        """Testa configuração válida."""
        config = TWSConfig(
            hostname="localhost",
            port=1619,
            username="user",
            password="password",
            mock_mode=True,
        )
        config.validate()  # Não deve lançar exceção

    def test_invalid_hostname(self):
        """Testa hostname inválido."""
        config = TWSConfig(hostname="", port=1619, username="user", password="password")
        with pytest.raises(ValueError, match="TWS hostname is required"):
            config.validate()

    def test_invalid_port(self):
        """Testa porta inválida."""
        config = TWSConfig(
            hostname="localhost", port=70000, username="user", password="password"
        )
        with pytest.raises(ValueError, match="TWS port must be between 1 and 65535"):
            config.validate()

    def test_invalid_timeout(self):
        """Testa timeout inválido."""
        config = TWSConfig(
            hostname="localhost",
            port=1619,
            username="user",
            password="password",
            timeout=0,
        )
        with pytest.raises(ValueError, match="Timeout must be positive"):
            config.validate()


class TestTWSClientFactory:
    """Testes para TWSClientFactory."""

    def test_create_mock_client(self):
        """Testa criação de cliente mock."""
        config = TWSConfig(
            hostname="localhost",
            port=1619,
            username="user",
            password="password",
            mock_mode=True,
        )
        client = TWSClientFactory.create(config)
        assert isinstance(client, TestTWSClient)
        assert client.config.mock_mode is True

    def test_create_production_client(self):
        """Testa criação de cliente de produção."""
        config = TWSConfig(
            hostname="prod-server",
            port=1619,
            username="produser",
            password="prodpass",
            mock_mode=False,
        )
        client = TWSClientFactory.create(config)
        assert isinstance(client, ProductionTWSClient)
        assert client.config.mock_mode is False

    def test_create_from_settings(self):
        """Testa criação a partir de settings."""
        settings = MagicMock(
            spec=[
                "TWS_HOST",
                "TWS_PORT",
                "TWS_USER",
                "TWS_PASSWORD",
                "TWS_MOCK_MODE",
                "TWS_ENGINE_NAME",
                "TWS_ENGINE_OWNER",
            ]
        )
        settings.TWS_HOST = "testhost"
        settings.TWS_PORT = 1620
        settings.TWS_USER = "testuser"
        settings.TWS_PASSWORD = "testpass"
        settings.TWS_MOCK_MODE = True
        settings.TWS_ENGINE_NAME = "TEST_ENGINE"
        settings.TWS_ENGINE_OWNER = "testowner"

        client = TWSClientFactory.create_from_settings(settings)
        assert isinstance(client, TestTWSClient)
        assert client.config.hostname == "testhost"
        assert client.config.port == 1620
        assert client.config.username == "testuser"
        assert client.config.password == "testpass"

    def test_create_for_testing(self):
        """Testa criação para testes."""
        client = TWSClientFactory.create_for_testing()
        assert isinstance(client, TestTWSClient)
        assert client.config.mock_mode is True
        assert client.config.hostname == "localhost"
        assert client.config.port == 1619


class TestTestTWSClient:
    """Testes para TestTWSClient."""

    @pytest.fixture
    def config(self):
        return TWSConfig(
            hostname="localhost",
            port=1619,
            username="user",
            password="password",
            mock_mode=True,
        )

    @pytest.fixture
    def client(self, config):
        return TestTWSClient(config)

    @pytest.mark.asyncio
    async def test_connect(self, client):
        """Testa conexão mock."""
        result = await client.connect()
        assert result is True
        assert client._connected is True

    @pytest.mark.asyncio
    async def test_execute_command(self, client):
        """Testa execução de comando mock."""
        await client.connect()
        result = await client.execute_command("test command")
        assert result == "MOCK: test command executed successfully"
        assert "test command" in client.executed_commands

    @pytest.mark.asyncio
    async def test_get_job_status_default(self, client):
        """Testa obtenção de status de job padrão."""
        await client.connect()
        status = await client.get_job_status("job123")
        assert status["job_id"] == "job123"
        assert status["status"] == "COMPLETED"
        assert status["progress"] == 100

    @pytest.mark.asyncio
    async def test_get_job_status_custom(self, client):
        """Testa obtenção de status de job customizado."""
        await client.connect()
        client.job_statuses["job456"] = {
            "job_id": "job456",
            "status": "RUNNING",
            "progress": 50,
        }
        status = await client.get_job_status("job456")
        assert status["status"] == "RUNNING"
        assert status["progress"] == 50

    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Testa desconexão."""
        await client.connect()
        assert client._connected is True

        await client.disconnect()
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_execute_command_not_connected(self, client):
        """Testa execução sem conexão."""
        with pytest.raises(ConnectionError, match="Not connected to TWS"):
            await client.execute_command("test")

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Testa health check."""
        await client.connect()
        await client.execute_command("test command")

        health = await client.health_check()
        assert health["connected"] is True
        assert health["mock_mode"] is True
        assert health["executed_commands_count"] == 1


class TestProductionTWSClient:
    """Testes para ProductionTWSClient."""

    @pytest.fixture
    def config(self):
        return TWSConfig(
            hostname="prod-server",
            port=1619,
            username="produser",
            password="prodpass",
            mock_mode=False,
        )

    @pytest.fixture
    def client(self, config):
        return ProductionTWSClient(config)

    @pytest.mark.asyncio
    async def test_initialization(self, client):
        """Testa inicialização do cliente de produção."""
        assert client.config.hostname == "prod-server"
        assert client.config.mock_mode is False
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_connect_simulation(self, client):
        """Testa simulação de conexão (sem TWS real)."""
        result = await client.connect()
        assert result is True
        assert client._connected is True

    @pytest.mark.asyncio
    async def test_execute_command_not_connected(self, client):
        """Testa execução sem conexão."""
        with pytest.raises(ConnectionError, match="Not connected to TWS"):
            await client.execute_command("test")
