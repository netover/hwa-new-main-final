"""AI Agent management and orchestration.

This module provides comprehensive agent management functionality including:
- Agent registration and discovery
- Agent lifecycle management (load, unload, reload)
- Agent execution orchestration
- Agent configuration validation
- Performance monitoring and metrics
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional, List

import structlog

# Configure agent manager logger
agent_logger = structlog.get_logger("resync.agent_manager")


try:
    from agno.agent import Agent

    AGNO_AVAILABLE = True
except ImportError:
    AGNO_AVAILABLE = False

    class MockAgent:
        """Mock Agent class compatible with agno.Agent interface."""

        def __init__(
            self,
            tools: Any = None,
            model: Any = None,
            instructions: Any = None,
            name: str = "Mock Agent",
            description: str = "Mock agent for testing",
            **kwargs: Any,
        ) -> None:
            # Initialize all required attributes
            self.tools = tools or []
            self.model = model
            self.llm_model = model  # Alias para compatibilidade com FastAPI
            self.instructions = instructions
            self.name = name
            self.description = description

            # Additional attributes that FastAPI might expect
            self.role = "Mock Agent"
            self.goal = "Provide mock responses for testing"
            self.backstory = description

        async def arun(self, message: str) -> str:
            """Process a message and return a response."""
            agent_logger.debug(
                "mock_agent_processing_message", message=message, agent_name=self.name
            )
            try:
                msg = message.lower()
                agent_logger.debug(
                    "mock_agent_message_normalized",
                    original_message=message,
                    normalized_message=msg,
                )

                if "job" in msg and ("abend" in msg or "erro" in msg):
                    result = "Jobs em estado ABEND encontrados:\\n- Data Processing (ID: JOB002) na workstation TWS_AGENT2\\n\\nRecomendo investigar o log do job e verificar dependências."
                    agent_logger.info(
                        "mock_agent_abend_response",
                        agent_name=self.name,
                        result_preview=result[:50],
                    )
                    return result

                elif "status" in msg or "workstation" in msg:
                    result = "Status atual do ambiente TWS:\\n\\nWorkstations:\\n- TWS_MASTER: ONLINE\\n- TWS_AGENT1: ONLINE\\n- TWS_AGENT2: OFFLINE\\n\\nJobs:\\n- Daily Backup: SUCC (TWS_AGENT1)\\n- Data Processing: ABEND (TWS_AGENT2)\\n- Report Generation: SUCC (TWS_AGENT1)"
                    agent_logger.info(
                        "mock_agent_status_response",
                        agent_name=self.name,
                        result_preview=result[:50],
                    )
                    return result

                elif "tws" in msg:
                    result = f"Como {self.name}, posso ajudar com questões relacionadas ao TWS. Que informações você precisa?"
                    agent_logger.info(
                        "mock_agent_tws_response",
                        agent_name=self.name,
                        result_preview=result[:50],
                    )
                    return result

                else:
                    result = f"Entendi sua mensagem: '{message}'. Como {self.name}, estou aqui para ajudar com questões do TWS."
                    agent_logger.info(
                        "mock_agent_default_response",
                        agent_name=self.name,
                        result_preview=result[:50],
                    )
                    return result

            except Exception as e:
                result = f"Erro simples: {str(e)}"
                agent_logger.error(
                    "mock_agent_processing_error",
                    agent_name=self.name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return result

        def run(self, message: str) -> str:
            """Synchronous version of arun for compatibility."""
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import asyncio

                    async def run_async():
                        return await self.arun(message)

                    return asyncio.create_task(run_async())
                else:
                    return loop.run_until_complete(self.arun(message))
            except Exception:
                import asyncio

                return asyncio.run(self.arun(message))

        def to_dict(self) -> dict:
            """Convert agent to dictionary for serialization - required by FastAPI."""
            return {
                "name": self.name,
                "description": self.description,
                "model": str(self.model) if self.model else None,
                "llm_model": str(self.llm_model) if self.llm_model else None,
                "role": self.role,
                "goal": self.goal,
                "backstory": self.backstory,
                "tools": [str(t) for t in self.tools] if self.tools else [],
            }


from pydantic import BaseModel

from resync.core.exceptions import (
    AgentError,
)  # Renamed from AgentExecutionError for broader scope
from resync.core.exceptions import (
    ConfigurationError,
    InvalidConfigError,
    MissingConfigError,
    NetworkError,
    ParsingError,
)
from resync.core.metrics import runtime_metrics
from resync.services.mock_tws_service import MockTWSClient
from resync.services.tws_service import OptimizedTWSClient
from resync.settings import settings

from .global_utils import get_environment_tags, get_global_correlation_id

# --- Logging Setup ---
logger = structlog.get_logger(__name__)


# --- Pydantic Models for Agent Configuration ---
from resync.models.agents import AgentConfig, AgentType
from pydantic import BaseModel
from typing import List


class AgentsConfig(BaseModel):
    """Configuration model for multiple agents."""

    agents: List[AgentConfig] = []


# --- Agent Manager Class ---
class AgentManager:
    """
    Manages the lifecycle and operations of AI agents.
    Implements singleton pattern for thread-safe behavior.
    """

    _instance: Optional["AgentManager"] = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Thread-safe singleton implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    async def load_agents_from_config(self, config_path: str | None = None) -> None:
        """Loads agent configurations from settings or specified path."""
        # Implementation for loading agents from config

    async def get_agent(self, agent_id: str) -> Any:
        """Retrieves an agent by its ID."""
        # Check if agent already exists
        if agent_id in self.agents:
            return self.agents[agent_id]

        # Create agent on demand
        agent = await self._create_agent(agent_id)
        if agent:
            self.agents[agent_id] = agent
        return agent

    async def _create_agent(self, agent_id: str) -> Any:
        """Create an agent instance for the given ID."""
        try:
            # Get agent configuration
            agent_config = None
            for config in self.agent_configs:
                if config.id == agent_id:
                    agent_config = config
                    break

            if not agent_config:
                logger.warning(f"No configuration found for agent '{agent_id}'")
                return None

            # Get TWS client for tools
            if not self.tws_client:
                async with self._tws_init_lock:
                    if not self.tws_client:
                        from resync.core.fastapi_di import get_service
                        from resync.core.interfaces import ITWSClient

                        try:
                            self.tws_client = await get_service(ITWSClient)
                        except Exception as e:
                            logger.warning(f"Failed to get TWS client: {e}")
                            self.tws_client = None

            # Create agent with tools
            if AGNO_AVAILABLE:
                # Create real agent with tools
                agent = Agent(
                    model=agent_config.model_name,
                    tools=list(self.tools.values()),
                    instructions=f"You are a {agent_config.name} assistant for TWS operations. {agent_config.backstory}",
                    name=agent_config.name,
                )
                logger.info(f"Created real agent: {agent}")
                return agent
            else:
                # Create mock agent with ALL required attributes - FIXED
                agent = MockAgent(
                    tools=list(self.tools.values()),
                    model=agent_config.model_name,
                    instructions=f"You are a {agent_config.name} assistant for TWS operations. {agent_config.backstory}",
                    name=agent_config.name,
                    description=agent_config.backstory,  # ✅ PASSAR DESCRIPTION
                )
                logger.info(
                    f"Created mock agent: {agent}, has arun: {hasattr(agent, 'arun')}"
                )
                return agent

        except Exception as e:
            logger.error(f"Failed to create agent '{agent_id}': {e}")
            return None

    async def get_all_agents(self) -> list[AgentConfig]:
        """Returns the configuration of all loaded agents."""
        return self.agent_configs

    async def get_agent_config(self, agent_id: str) -> AgentConfig | None:
        """Retrieves the configuration of a specific agent by its ID."""
        for config in self.agent_configs:
            if config.id == agent_id:
                return config
        return None

    def _create_tws_client(self) -> Any:
        """Creates a TWS client instance."""
        from resync.core.fastapi_di import get_service
        from resync.core.interfaces import ITWSClient

        try:
            return get_service(ITWSClient)()
        except Exception as e:
            logger.warning(f"Failed to get TWS client: {e}")
            return None

    async def get_tws_client(self) -> Any:
        """Get or create TWS client with thread-safe initialization."""
        if not self.tws_client:
            async with self._tws_init_lock:
                if not self.tws_client:
                    self.tws_client = self._tws_client_factory()
        return self.tws_client

    def _discover_tools(self) -> dict[str, Any]:
        """Discover available tools for agents."""
        try:
            from resync.tool_definitions.tws_tools import (
                tws_status_tool,
                tws_troubleshooting_tool,
            )

            return {
                "get_tws_status": tws_status_tool.get_tws_status,
                "analyze_tws_failures": tws_troubleshooting_tool.analyze_failures,
            }
        except ImportError as e:
            logger.warning(f"Could not import TWS tools: {e}")
            return {}

    def __init__(
        self,
        settings_module: Any = settings,
        tws_client_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """
        Initializes the AgentManager with thread-safe initialization.
        """
        with self._lock:
            if not self._initialized:
                self._initialized = True
                self._tws_client_factory = tws_client_factory or self._create_tws_client

                global_correlation = get_global_correlation_id()
                correlation_id = runtime_metrics.create_correlation_id(
                    {
                        "component": "agent_manager",
                        "operation": "init",
                        "global_correlation": global_correlation,
                        "environment": get_environment_tags(),
                    }
                )

                try:
                    # Fail-fast check: No MockAgent in production
                    if not AGNO_AVAILABLE:
                        runtime_metrics.agent_mock_fallbacks.increment()
                        is_production = (
                            getattr(
                                settings_module, "ENVIRONMENT", "development"
                            ).lower()
                            == "production"
                        )
                        if is_production:
                            error_msg = "CRITICAL: agno.agent not available in production environment. Cannot proceed with MockAgent fallback."
                            logger.critical(
                                "agno_agent_unavailable_production",
                                error=error_msg,
                                correlation_id=correlation_id,
                            )
                            runtime_metrics.record_health_check(
                                "agent_manager",
                                "critical",
                                {"error": "agno_unavailable_production"},
                            )
                            raise AgentError(error_msg)

                        logger.warning(
                            "agno_agent_not_available_non_production",
                            message="agno.agent not available in non-production environment. Using MockAgent fallback.",
                            correlation_id=correlation_id,
                        )
                        runtime_metrics.record_health_check(
                            "agent_manager", "degraded", {"mock_fallback": True}
                        )

                    logger.info("initializing_agent_manager")
                    runtime_metrics.record_health_check("agent_manager", "initializing")

                    self.settings = settings_module
                    self.agents: dict[str, Any] = {}
                    # Load default agent configurations
                    self.agent_configs: list[AgentConfig] = [
                        AgentConfig(
                            id="tws-troubleshooting",
                            name="TWS Troubleshooting Agent",
                            agent_type=AgentType.TASK,
                            role="TWS Troubleshooting Specialist",
                            goal="Help users identify and resolve TWS system issues",
                            backstory="I am an expert AI assistant specialized in IBM Workload Automation (TWS) troubleshooting and system monitoring.",
                            tools=["get_tws_status", "analyze_tws_failures"],
                            model_name="tongyi-deepresearch",
                            temperature=0.7,
                            memory=True,
                            verbose=False,
                        ),
                        AgentConfig(
                            id="tws-general",
                            name="TWS General Assistant",
                            agent_type=AgentType.CHAT,
                            role="TWS General Assistant",
                            goal="Provide general assistance for TWS operations and monitoring",
                            backstory="I am a helpful AI assistant for IBM Workload Automation (TWS) operations, providing information about system status and job execution.",
                            tools=["get_tws_status", "analyze_tws_failures"],
                            model_name="openrouter-fallback",
                            temperature=0.5,
                            memory=True,
                            verbose=False,
                        ),
                    ]
                    self.tools: dict[str, Any] = self._discover_tools()
                    self.tws_client: Optional[OptimizedTWSClient] = None
                    self._mock_tws_client: Optional[MockTWSClient] = None
                    # Async lock to prevent race conditions during TWS client initialization
                    self._tws_init_lock: asyncio.Lock = asyncio.Lock()

                    runtime_metrics.record_health_check("agent_manager", "healthy")
                    logger.info(
                        "agent_manager_initialized_successfully",
                        correlation_id=correlation_id,
                    )

                except AgentError as e:
                    # Capture specific, known critical errors during initialization
                    runtime_metrics.record_health_check(
                        "agent_manager", "failed", {"error": str(e)}
                    )
                    logger.critical(
                        "agent_manager_initialization_failed",
                        error=str(e),
                        correlation_id=correlation_id,
                        exc_info=True,
                    )
                    raise  # Re-raise the specific AgentError
                finally:
                    runtime_metrics.close_correlation_id(correlation_id)


# Global singleton instance for backwards compatibility
agent_manager = AgentManager()
