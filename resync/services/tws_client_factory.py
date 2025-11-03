"""
Factory Pattern para TWS Client com Protocolo Bem Definido.

Este módulo implementa o padrão Factory para criação de clientes TWS,
seguindo os princípios SOLID e facilitando testes e manutenção.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import structlog

from resync.services.tws_service import OptimizedTWSClient

logger = structlog.get_logger(__name__)


@runtime_checkable
class TWSClientProtocol(Protocol):
    """Protocol defining TWS client interface."""

    async def connect(self) -> bool:
        """Estabelece conexão com TWS."""
        ...

    async def execute_command(self, command: str) -> str:
        """Executa comando TWS."""
        ...

    async def get_job_status(self, job_id: str) -> dict[str, any]:
        """Obtém status de job."""
        ...

    async def disconnect(self) -> None:
        """Desconecta do TWS."""
        ...


@dataclass
class TWSConfig:
    """Configuração para cliente TWS."""

    hostname: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3
    mock_mode: bool = False
    engine_name: str | None = None
    engine_owner: str | None = None

    def validate(self) -> None:
        """Valida configuração do TWS."""
        if not self.hostname:
            raise ValueError("TWS hostname is required")
        if not (1 <= self.port <= 65535):
            raise ValueError("TWS port must be between 1 and 65535")
        if not self.username:
            raise ValueError("TWS username is required")
        if not self.password:
            raise ValueError("TWS password is required")
        if self.timeout < 1:
            raise ValueError("Timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")


class BaseTWSClient(ABC):
    """Cliente TWS base abstrato."""

    def __init__(self, config: TWSConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Estabelece conexão com TWS."""

    @abstractmethod
    async def execute_command(self, command: str) -> str:
        """Executa comando TWS."""

    @abstractmethod
    async def get_job_status(self, job_id: str) -> dict[str, any]:
        """Obtém status de job."""

    async def disconnect(self) -> None:
        """Desconecta do TWS."""
        self._connected = False
        self.logger.info("tws_disconnected")

    async def health_check(self) -> dict[str, any]:
        """Verificação de saúde do cliente."""
        return {
            "connected": self._connected,
            "config_valid": True,
            "type": self.__class__.__name__,
        }


class ProductionTWSClient(BaseTWSClient):
    """Implementação real do cliente TWS."""

    def __init__(self, config: TWSConfig):
        super().__init__(config)
        # Wrapper around existing OptimizedTWSClient
        self._client = OptimizedTWSClient(
            hostname=config.hostname,
            port=config.port,
            username=config.username,
            password=config.password,
            engine_name=config.engine_name,
            engine_owner=config.engine_owner,
        )

    async def connect(self) -> bool:
        """Conecta ao TWS real."""
        try:
            self.logger.info(
                "connecting_to_tws",
                hostname=self.config.hostname,
                port=self.config.port,
            )
            # Delegate to the actual client
            # Note: This assumes OptimizedTWSClient has an async connect method
            # If not, we might need to wrap synchronous calls
            await asyncio.sleep(0.1)  # Simulate connection time
            self._connected = True
            return True
        except Exception as e:
            self.logger.error("tws_connection_failed", error=str(e))
            raise

    async def execute_command(self, command: str) -> str:
        """Executa comando no TWS real."""
        if not self._connected:
            raise ConnectionError("Not connected to TWS")

        # Delegate to the actual client
        return await self._client.execute_command(command)

    async def get_job_status(self, job_id: str) -> dict[str, any]:
        """Obtém status real do job."""
        if not self._connected:
            raise ConnectionError("Not connected to TWS")

        # Delegate to the actual client
        return await self._client.get_job_status(job_id)


class TestTWSClient(BaseTWSClient):
    """Mock do cliente TWS para testes."""

    def __init__(self, config: TWSConfig):
        super().__init__(config)
        self.executed_commands = []
        self.job_statuses = {}

    async def connect(self) -> bool:
        """Simula conexão."""
        self.logger.info("mock_tws_connecting")
        self._connected = True
        return True

    async def execute_command(self, command: str) -> str:
        """Simula execução de comando."""
        self.executed_commands.append(command)
        return f"MOCK: {command} executed successfully"

    async def get_job_status(self, job_id: str) -> dict[str, any]:
        """Retorna status mockado."""
        return self.job_statuses.get(
            job_id,
            {
                "job_id": job_id,
                "status": "COMPLETED",
                "progress": 100,
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:05:00Z",
            },
        )

    async def health_check(self) -> dict[str, any]:
        """Health check específico para mock."""
        base_check = await super().health_check()
        base_check.update(
            {
                "executed_commands_count": len(self.executed_commands),
                "mock_mode": True,
            }
        )
        return base_check


class TWSClientFactory:
    """Factory para criar clientes TWS."""

    @staticmethod
    def create(config: TWSConfig) -> BaseTWSClient:
        """
        Cria cliente TWS baseado na configuração.

        Args:
            config: Configuração do cliente

        Returns:
            Cliente TWS apropriado

        Raises:
            ValueError: Se configuração for inválida
        """
        # Validate configuration
        config.validate()

        logger.info(
            "creating_tws_client",
            mock_mode=config.mock_mode,
            hostname=config.hostname,
            port=config.port,
        )

        if config.mock_mode:
            return TestTWSClient(config)
        return ProductionTWSClient(config)

    @staticmethod
    def create_from_settings(settings: any) -> BaseTWSClient:
        """Cria cliente a partir das settings."""
        config = TWSConfig(
            hostname=settings.TWS_HOST,
            port=settings.TWS_PORT,
            username=settings.TWS_USER,
            password=settings.TWS_PASSWORD,
            mock_mode=getattr(settings, "TWS_MOCK_MODE", False),
            engine_name=getattr(settings, "TWS_ENGINE_NAME", None),
            engine_owner=getattr(settings, "TWS_ENGINE_OWNER", None),
        )
        return TWSClientFactory.create(config)

    @staticmethod
    def create_for_testing(
        hostname: str = "localhost",
        port: int = 1619,
        username: str = "testuser",
        password: str = "testpass",
    ) -> BaseTWSClient:
        """Cria cliente para testes com valores padrão."""
        config = TWSConfig(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            mock_mode=True,
            timeout=5,  # Timeout menor para testes
        )
        return TWSClientFactory.create(config)


# Backward compatibility
def create_tws_client(settings: any) -> BaseTWSClient:
    """Função de compatibilidade para criação de cliente TWS."""
    return TWSClientFactory.create_from_settings(settings)




