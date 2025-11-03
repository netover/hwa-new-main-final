# resync/core/utils/llm.py

from litellm.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
)

from ...settings import settings
from ..resilience import circuit_breaker, retry_with_backoff, with_timeout
from ..structured_logger import get_logger
from .common_error_handlers import retry_on_exception
from .llm_factories import LLMFactory

logger = get_logger(__name__)


@circuit_breaker(failure_threshold=3, recovery_timeout=60, name="llm_service")
@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0, jitter=True)
@with_timeout(settings.LLM_TIMEOUT)
@retry_on_exception(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(
        AuthenticationError,
        RateLimitError,
        APIError,
        ConnectionError,
        TimeoutError,
        ValueError,
        Exception,
    ),
    logger=logger,
)
async def call_llm(
    prompt: str,
    model: str,
    max_tokens: int = 200,
    temperature: float = 0.1,
    max_retries: int = 3,
    _initial_backoff: float = 1.0,
    api_base: str = None,
    api_key: str = None,
    timeout: float = 30.0,
) -> str:
    """
    Calls an LLM through LiteLLM with support for multiple providers (OpenAI, Ollama, etc.).
    Provides enhanced error handling, cost tracking, and model flexibility.

    Args:
        prompt: The prompt to send to the LLM.
        model: The LLM model to use (e.g., "gpt-4o", "ollama/mistral", etc.).
        max_tokens: Maximum number of tokens in the LLM's response.
        temperature: Controls the randomness of the LLM's response.
        max_retries: Maximum number of retry attempts for the LLM call.
        initial_backoff: Initial delay in seconds before the first retry.
        api_base: Optional API base URL (for local models like Ollama).
        api_key: Optional API key (defaults to settings if not provided).
        timeout: Maximum time in seconds to wait for the LLM response.

    Returns:
        The content of the LLM's response.

    Raises:
        LLMError: If the LLM call fails after all retry attempts or times out.
    """
    return await LLMFactory.call_llm(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=max_retries,
        _initial_backoff=_initial_backoff,
        api_base=api_base,
        api_key=api_key,
        timeout=timeout,
    )




