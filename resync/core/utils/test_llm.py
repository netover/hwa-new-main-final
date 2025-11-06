from unittest.mock import AsyncMock, MagicMock

import pytest

from ..exceptions import LLMError
from .llm import call_llm

# Marks all tests in this file as async
pytestmark = pytest.mark.asyncio


async def test_call_llm_success(mocker):
    """
    Tests the happy path where the LLM call succeeds on the first attempt.
    """
    # Mock the response from LiteLLM
    mock_choice = MagicMock()
    mock_choice.message.content = "  Mocked LLM Response  "
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 20}

    # Patch the LiteLLM acompletion function to return our mock response
    mock_acompletion = AsyncMock(return_value=mock_response)
    mocker.patch("resync.core.utils.llm_factories.acompletion", mock_acompletion)

    # Mock the router to avoid the fallback response
    mock_router = MagicMock()
    mock_router.model_list = ["test-model"]
    mocker.patch(
        "resync.core.litellm_init.get_litellm_router", return_value=mock_router
    )

    # Call the function
    result = await call_llm(prompt="test prompt", model="test-model")

    # Assertions
    assert result == "Mocked LLM Response"
    mock_acompletion.assert_called_once()


async def test_call_llm_raises_llmerror_after_retries_on_apierror(mocker):
    """
    Ensures LLMError is raised after all retries fail due to an APIError.
    This tests the primary error handling path for API-specific issues.
    """
    # Mock the LLMFactory.call_llm method directly to control retry behavior
    # Make it raise LLMError directly since that's what the retry decorators expect
    mock_factory_call = AsyncMock(
        side_effect=LLMError(
            message="API error: litellm.APIError: API is down", model_name="test-model"
        )
    )
    mocker.patch(
        "resync.core.utils.llm_factories.LLMFactory.call_llm", mock_factory_call
    )

    # Call the function and assert that it raises our custom LLMError
    with pytest.raises(LLMError):
        await call_llm(
            prompt="test", model="test-model", max_retries=2, initial_backoff=0.01
        )

    # Calculate expected calls:
    # retry_on_exception: 1 initial + 2 retries = 3 calls (max_retries=2)
    # retry_with_backoff: 1 initial + 3 retries = 4 calls (default max_retries=3)
    # Total expected: 3 x 4 = 12 calls
    assert mock_factory_call.call_count == 12


async def test_call_llm_raises_llmerror_after_retries_on_network_error(mocker):
    """
    Ensures LLMError is raised after all retries fail due to a network error.
    This tests the handling of connection-related issues.
    """
    # Mock the LLMFactory.call_llm method directly to control retry behavior
    # Make it raise LLMError directly since that's what the retry decorators expect
    mock_factory_call = AsyncMock(
        side_effect=LLMError(
            message="Unexpected error: litellm.APIConnectionError: Network error",
            model_name="test-model",
        )
    )
    mocker.patch(
        "resync.core.utils.llm_factories.LLMFactory.call_llm", mock_factory_call
    )

    # Call the function and assert that it raises our custom LLMError
    with pytest.raises(LLMError):
        await call_llm(
            prompt="test", model="test-model", max_retries=1, initial_backoff=0.01
        )

    # Calculate expected calls:
    # retry_on_exception: 1 initial + 1 retry = 2 calls (max_retries=1)
    # retry_with_backoff: 1 initial + 3 retries = 4 calls (default max_retries=3)
    # Total expected: 2 x 4 = 8 calls
    assert mock_factory_call.call_count == 8
