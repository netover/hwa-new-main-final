"""
LiteLLM Initialization Module

This module provides LiteLLM router initialization and configuration.
For development purposes, this provides a mock router when LiteLLM is not available.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MockModelInfo:
    """Mock model information for development."""

    model_name: str
    litellm_params: Dict[str, Any]
    model_info: Dict[str, Any]


class MockLiteLLMRouter:
    """
    Mock LiteLLM router for development when LiteLLM is not available.

    This provides the same interface as the real LiteLLM router.
    """

    def __init__(self):
        # Mock some common models for development
        self.model_list: List[MockModelInfo] = [
            MockModelInfo(
                model_name="gpt-3.5-turbo",
                litellm_params={"model": "gpt-3.5-turbo", "api_key": "mock_key"},
                model_info={"max_tokens": 4096, "input_cost_per_token": 0.0015}
            ),
            MockModelInfo(
                model_name="gpt-4",
                litellm_params={"model": "gpt-4", "api_key": "mock_key"},
                model_info={"max_tokens": 8192, "input_cost_per_token": 0.03}
            ),
        ]

    def __bool__(self) -> bool:
        """Return True if router has models."""
        return len(self.model_list) > 0


def get_litellm_router() -> Optional[MockLiteLLMRouter]:
    """
    Get the LiteLLM router instance.

    In production, this should initialize the real LiteLLM router.
    For development, this returns a mock router.

    Returns:
        LiteLLM router instance or None if not available
    """
    try:
        # Try to import real LiteLLM
        from litellm import Router

        # In a real implementation, this would configure the router
        # with actual model configurations from settings
        router = Router(model_list=[
            {
                "model_name": "gpt-3.5-turbo",
                "litellm_params": {
                    "model": "gpt-3.5-turbo",
                    "api_key": "your-openai-api-key"  # Should come from config
                }
            }
        ])
        return router

    except ImportError:
        # LiteLLM not available, return mock router for development
        return MockLiteLLMRouter()


def initialize_litellm() -> None:
    """
    Initialize LiteLLM with configuration.

    This should be called during application startup.
    """
    try:
        from litellm import set_verbose
        # Configure LiteLLM (would use actual settings in production)
        set_verbose(False)
    except ImportError:
        # LiteLLM not available, skip initialization
        pass
