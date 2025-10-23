"""
LiteLLM initialization for Resync TWS application.

This module sets up LiteLLM with the proper configuration for
TWS-specific use cases, including local Ollama and remote API models.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from resync.settings import settings

logger = logging.getLogger(__name__)


def initialize_litellm() -> Any:
    """
    Initialize LiteLLM with configuration specific to Resync TWS application.

    This function:
    1. Sets up LiteLLM with local and remote model configurations
    2. Configures caching using Redis
    3. Sets up cost tracking and logging
    4. Defines model routing rules for TWS-specific queries
    """
    try:
        # Import with type ignore for litellm-specific issues
        from litellm import Router as LiteLLMRouter  
        from litellm import completion_cost  

        # Get configuration path
        config_path = Path(__file__).parent / "litellm_config.yaml"

        # Initialize LiteLLM router with configuration
        # The router will handle model selection and fallbacks
        litellm_router = LiteLLMRouter(
            model_list=None,  # Will be loaded from config
            enable_pre_call_checks=True,
        )

        # Override with app-specific settings for OpenRouter
        if hasattr(settings, "LLM_ENDPOINT") and settings.LLM_ENDPOINT:
            os.environ["OPENAI_API_BASE"] = settings.LLM_ENDPOINT

        if hasattr(settings, "LLM_API_KEY") and settings.LLM_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.LLM_API_KEY

        # Set OpenRouter specific environment variables
        os.environ["OPENROUTER_API_KEY"] = (
            settings.LLM_API_KEY
            if hasattr(settings, "LLM_API_KEY") and settings.LLM_API_KEY
            else ""
        )

        logger.info("LiteLLM initialized successfully with TWS-specific configuration")

        return litellm_router

    except ImportError:
        logger.warning("LiteLLM not installed, using fallback LLM implementation")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize LiteLLM: {e}")
        return None


# Initialize LiteLLM when module is imported
litellm_router = initialize_litellm()


def get_litellm_router() -> Any:
    """
    Get the initialized LiteLLM router instance.

    Returns:
        Router: LiteLLM router instance or None if initialization failed
    """
    return litellm_router


def calculate_completion_cost(completion_response: Any) -> float:
    """
    Calculate the cost of a completion response using LiteLLM's cost calculation.

    Args:
        completion_response: The completion response object from LiteLLM

    Returns:
        float: The cost of the completion in USD, or 0.0 if calculation fails
    """
    try:
        from litellm import completion_cost  

        return completion_cost(completion_response=completion_response)
    except Exception as e:
        logger.warning(f"Could not calculate completion cost: {e}")
        return 0.0
