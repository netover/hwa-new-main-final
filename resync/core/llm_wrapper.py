"""Optimized LLM wrapper shim.

This module provides a minimal wrapper around the LLM factory to
maintain compatibility with older imports of ``resync.core.llm_wrapper``.
The original implementation exposed an object called ``optimized_llm``
with a ``get_response`` coroutine used to generate optimized
responses for LLM queries.  In this simplified version we rely on
``resync.utils.llm_factories.LLMFactory`` and the configured model
name from the application settings.  If an LLM call fails or a model
is not available, the original query is returned unchanged.
"""

from __future__ import annotations

from typing import Any, Optional

from resync.settings import settings
from resync.utils.llm_factories import LLMFactory


class OptimizedLLM:
    """Facade for optimized LLM calls.

    Provides a ``get_response`` coroutine that attempts to call the
    configured LLM via the factory.  On failure, returns the input
    query unchanged.  Additional context, caching or streaming
    functionality may be implemented in future versions.
    """

    async def get_response(
        self,
        *,
        query: str,
        context: Optional[dict[str, Any]] = None,
        use_cache: bool = True,
        stream: bool = False,
    ) -> str:
        """Get an optimized LLM response for a given query.

        Args:
            query: The user query or prompt
            context: Optional context dictionary (currently ignored)
            use_cache: Whether to enable caching (currently ignored)
            stream: Whether to stream the response (currently ignored)

        Returns:
            The LLM response if successful, otherwise the original query
        """
        # Determine which model to use – fall back to agent_model_name
        model_name = getattr(settings, "agent_model_name", None)
        if not model_name:
            model_name = "gpt-4o"
        try:
            response = await LLMFactory.call_llm(
                prompt=query,
                model=model_name,
            )
            return response
        except Exception:
            # In case of error (e.g. missing LLM configuration), return original query
            return query


# Instantiate a module‑level singleton for backward compatibility
optimized_llm = OptimizedLLM()

__all__ = ["OptimizedLLM", "optimized_llm"]
