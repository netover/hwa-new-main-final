"""
LLM Service using OpenAI for NVIDIA API Integration

This service provides a unified interface for interacting with NVIDIA API
through OpenAI library, which has been tested and confirmed to work.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from functools import lru_cache, wraps
from typing import Any

from resync.settings.settings import settings
from resync.utils.exceptions import IntegrationError

try:
    # Import specific exceptions from OpenAI v1.x
    from openai import (
        APIConnectionError,
        APIError,
        APIStatusError,
        APITimeoutError,
        AsyncOpenAI,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )

    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


# Circuit Breaker Implementation
class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""


class CircuitState:
    """Circuit breaker state enumeration."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, blocking calls
    HALF_OPEN = "half_open"  # Testing if service has recovered


class SimpleCircuitBreaker:
    """
    Simple circuit breaker implementation for protecting against cascading failures.
    """

    def __init__(self, failure_threshold: int = 3, timeout: int = 30):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before transitioning from OPEN to HALF_OPEN
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def __call__(self, func):
        """Decorator to apply circuit breaker to a function."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerError("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        import time

        return (time.time() - self.last_failure_time) >= self.timeout

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker transitioning to CLOSED")

    def _on_failure(self):
        """Handle failed call."""
        import time

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker transitioning to OPEN after {self.failure_count} failures"
            )

    def get_state(self) -> str:
        """Get current circuit breaker state."""
        return self.state

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
        }


def _coerce_secret(value: Any) -> str | None:
    """Accept str or pydantic SecretStr; return plain str or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    # pydantic SecretStr compatibility
    get_secret = getattr(value, "get_secret_value", None)
    return get_secret() if callable(get_secret) else str(value)


class LLMService:
    """Service for interacting with LLM APIs through OpenAI-compatible endpoints."""

    def __init__(self) -> None:
        """Initialize LLM service with NVIDIA API configuration"""
        if not OPENAI_AVAILABLE:
            raise IntegrationError(
                message="openai package is required but not installed",
                details={"install_command": "pip install openai"},
            )

        # --- Model resolution with fallbacks ---
        model = getattr(settings, "llm_model", None)
        if model is None:
            model = getattr(settings, "agent_model_name", None)
        if not model:
            raise IntegrationError(
                message="No LLM model configured",
                details={
                    "hint": "Define settings.llm_model or settings.agent_model_name"
                },
            )
        self.model: str = str(model)

        # Defaults
        self.default_temperature = 0.6
        self.default_top_p = 0.95
        self.default_max_tokens = 1000
        self.default_frequency_penalty = 0.0
        self.default_presence_penalty = 0.0

        # --- API key / endpoint (NVIDIA OpenAI-compatible) ---
        api_key = _coerce_secret(getattr(settings, "llm_api_key", None))
        base_url = getattr(settings, "llm_endpoint", None)
        if not base_url:
            raise IntegrationError(
                message="Missing LLM base_url",
                details={
                    "hint": "Configure settings.llm_endpoint (NVIDIA OpenAI-compatible)"
                },
            )

        if api_key:
            masked = (api_key[:4] + "...") if len(api_key) > 4 else "***"
            logger.info("Using LLM API key: %s", masked)
        else:
            logger.info("No LLM API key configured")
        logger.info("LLM base URL: %s", base_url)

        # Initialize circuit breaker for LLM calls
        self.circuit_breaker = SimpleCircuitBreaker(
            failure_threshold=3, timeout=30
        )

        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=20.0,  # Default do SDK é 10 min; produção costuma usar valores menores
                max_retries=2,  # README mostra como ajustar (global/per-request)
            )
            logger.info("LLM service initialized with model: %s", self.model)
        except (
            AuthenticationError,
            RateLimitError,
            APIConnectionError,
            BadRequestError,
            APIError,
            APITimeoutError,
            APIStatusError,
        ) as exc:
            logger.error(
                "Failed to initialize LLM service (OpenAI error): %s",
                exc,
                exc_info=True,
            )
            raise IntegrationError(
                message="Failed to initialize LLM service",
                details={
                    "error": str(exc),
                    "request_id": getattr(exc, "request_id", None),
                },
            ) from exc
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to initialize LLM service: %s", exc, exc_info=True
            )
            raise IntegrationError(
                message="Failed to initialize LLM service",
                details={"error": str(exc)},
            ) from exc

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        stream: bool = False,
    ) -> str:
        """
        Generate a response from LLM

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            top_p: Nucleus sampling parameter (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            frequency_penalty: Frequency penalty (-2.0 to 2.0)
            presence_penalty: Presence penalty (-2.0 to 2.0)
            stream: Whether to stream response

        Returns:
            Generated text response
        """
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # Required for OpenAI API compatibility - all parameters are needed
        temperature = (
            self.default_temperature if temperature is None else temperature
        )
        top_p = self.default_top_p if top_p is None else top_p
        max_tokens = (
            self.default_max_tokens if max_tokens is None else max_tokens
        )
        frequency_penalty = (
            self.default_frequency_penalty
            if frequency_penalty is None
            else frequency_penalty
        )
        presence_penalty = (
            self.default_presence_penalty
            if presence_penalty is None
            else presence_penalty
        )

        logger.info("Generating LLM response with model: %s", self.model)

        # Apply circuit breaker to protect against cascading failures
        @self.circuit_breaker
        async def _generate_with_circuit_breaker():
            try:
                if stream:
                    # Aggregate all chunks and return complete response
                    chunks: list[str] = []
                    async for piece in self._generate_response_streaming(
                        messages,
                        temperature,
                        top_p,
                        max_tokens,
                        frequency_penalty,
                        presence_penalty,
                    ):
                        chunks.append(piece)
                    content = "".join(chunks)
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,  # NVIDIA: keep explicit (known bug)
                        frequency_penalty=frequency_penalty,
                        presence_penalty=presence_penalty,
                        stream=False,
                    )
                    content = response.choices[0].message.content or ""

                logger.info(
                    "Generated LLM response (%d characters)", len(content)
                )
                return content

            except (
                AuthenticationError,
                RateLimitError,
                APIConnectionError,
                BadRequestError,
                APIError,
                APITimeoutError,
                APIStatusError,
            ) as exc:
                logger.error(
                    "Error generating LLM response: %s", exc, exc_info=True
                )
                raise IntegrationError(
                    message="Failed to generate LLM response",
                    details={
                        "error": str(exc),
                        "request_id": getattr(exc, "request_id", None),
                        "model": self.model,
                    },
                ) from exc
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Unexpected error generating LLM response: %s",
                    exc,
                    exc_info=True,
                )
                raise IntegrationError(
                    message="Failed to generate LLM response",
                    details={"error": str(exc), "model": self.model},
                ) from exc

        try:
            return await _generate_with_circuit_breaker()
        except CircuitBreakerError as e:
            logger.error("Circuit breaker is OPEN: %s", e)
            raise IntegrationError(
                message="LLM service temporarily unavailable due to repeated failures",
                details={
                    "error": str(e),
                    "circuit_breaker_state": self.circuit_breaker.get_state(),
                    "model": self.model,
                },
            ) from e

    async def _generate_response_streaming(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        frequency_penalty: float,
        presence_penalty: float,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from LLM

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            max_tokens: Maximum number of tokens to generate
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty

        Yields:
            Chunks of generated response
        """
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # Required for OpenAI API compatibility - all parameters are needed
        logger.info(
            "Generating streaming LLM response with model: %s", self.model
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,  # NVIDIA: keep explicit
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    yield delta.content  # type: ignore[no-any-return]
        except (
            AuthenticationError,
            RateLimitError,
            APIConnectionError,
            BadRequestError,
            APIError,
            APITimeoutError,
            APIStatusError,
        ) as exc:
            logger.error(
                "Error generating streaming LLM response: %s",
                exc,
                exc_info=True,
            )
            raise IntegrationError(
                message="Failed to generate streaming LLM response",
                details={
                    "error": str(exc),
                    "request_id": getattr(exc, "request_id", None),
                    "model": self.model,
                },
            ) from exc
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Unexpected error generating streaming LLM response: %s",
                exc,
                exc_info=True,
            )
            raise IntegrationError(
                message="Failed to generate streaming LLM response",
                details={"error": str(exc), "model": self.model},
            ) from exc

    async def generate_system_status_message(
        self, system_info: dict[str, Any]
    ) -> str:
        """
        Generate a status message about system

        Args:
            system_info: Dictionary containing system information

        Returns:
            Generated status message
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "Você é um assistente de IA do sistema Resync TWS Integration. "
                    "Forneça informações claras e concisas sobre o status do sistema "
                    "em português brasileiro. Seja profissional e útil."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Por favor, forneça um resumo do status atual do sistema com base "
                    f"nestas informações: {system_info}"
                ),
            },
        ]
        return await self.generate_response(messages, max_tokens=500)

    async def generate_agent_response(
        self,
        agent_id: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a response from an AI agent

        Args:
            agent_id: ID of agent
            user_message: User's message
            conversation_history: Previous conversation history
            agent_config: Agent configuration

        Returns:
            Generated agent response
        """
        agent_type = (agent_config or {}).get("type", "general")
        agent_name = (agent_config or {}).get("name", f"Agente {agent_id}")
        agent_description = (agent_config or {}).get(
            "description", f"Assistente {agent_type}"
        )

        system_message = (
            f"Você é {agent_name}, {agent_description}. "
            "Responda de forma útil e profissional em português brasileiro. "
            "Seja conciso e forneça informações precisas."
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_message}
        ]
        if conversation_history:
            messages.extend(conversation_history[-5:])  # últimas 5

        messages.append({"role": "user", "content": user_message})
        return await self.generate_response(messages, max_tokens=800)

    async def generate_rag_response(
        self,
        query: str,
        context: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Generate a response using RAG (Retrieval-Augmented Generation)

        Args:
            query: User's query
            context: Retrieved context/documents
            conversation_history: Previous conversation history

        Returns:
            Generated RAG response
        """
        system_message = (
            "Você é um assistente de IA especializado em responder perguntas "
            "baseado no contexto fornecido. Use as informações do contexto para "
            "responder de forma precisa e útil. Se o contexto não contiver "
            "informações suficientes, diga que não sabe. Responda em português brasileiro."
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_message}
        ]
        if conversation_history:
            messages.extend(conversation_history[-3:])

        contextual_query = (
            f"Contexto relevante:\n{context}\n\nPergunta do usuário: {query}"
        )
        messages.append({"role": "user", "content": contextual_query})
        return await self.generate_response(messages, max_tokens=1000)

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on LLM service

        Returns:
            Dictionary containing health status information
        """
        try:
            test_response = await self.generate_response(
                messages=[
                    {"role": "user", "content": "Responda apenas com 'OK'."}
                ],
                max_tokens=10,  # keep explicit (NVIDIA)
            )
            ok = test_response.strip() == "OK"
            status = "healthy" if ok else "degraded"
            result: dict[str, Any] = {
                "status": status,
                "model": self.model,
                "endpoint": getattr(settings, "llm_endpoint", None),
                "test_response": test_response,
                "circuit_breaker": self.circuit_breaker.get_stats(),
            }
            if not ok:
                result["error"] = "Unexpected response"
            return result
        except CircuitBreakerError as e:
            return {
                "status": "unhealthy",
                "model": self.model,
                "endpoint": getattr(settings, "llm_endpoint", None),
                "error": str(e),
                "circuit_breaker": self.circuit_breaker.get_stats(),
            }
        except (
            AuthenticationError,
            RateLimitError,
            APIConnectionError,
            BadRequestError,
            APIError,
            APITimeoutError,
            APIStatusError,
        ) as exc:
            return {
                "status": "unhealthy",
                "model": self.model,
                "endpoint": getattr(settings, "llm_endpoint", None),
                "error": str(exc),
                "request_id": getattr(exc, "request_id", None),
                "circuit_breaker": self.circuit_breaker.get_stats(),
            }
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return {
                "status": "unhealthy",
                "model": self.model,
                "endpoint": getattr(settings, "llm_endpoint", None),
                "error": str(exc),
                "circuit_breaker": self.circuit_breaker.get_stats(),
            }

    async def chat_completion(
        self,
        user_message: str,
        agent_id: str,
        agent_config: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        stream: bool = False,  # pylint: disable=unused-argument
    ) -> str:
        """
        Simplified chat completion method

        Args:
            user_message: User's message
            agent_id: ID of agent
            agent_config: Agent configuration
            conversation_history: Previous conversation history
            stream: Whether to stream response (not used in current implementation)

        Returns:
            Generated response
        """
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # Required for API compatibility - all parameters are needed
        return await self.generate_agent_response(
            agent_id=agent_id,
            user_message=user_message,
            conversation_history=conversation_history,
            agent_config=agent_config,
        )

    async def aclose(self) -> None:
        """Close underlying HTTP resources of the OpenAI client."""
        if hasattr(self.client, "close"):
            self.client.close()
        # AsyncOpenAI v1 doesn't have explicit close method
        # Resources are cleaned up automatically when the client is garbage collected


# Singleton idempotente, sem globals mutáveis
@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """Get or create global LLM service instance."""
    return LLMService()








