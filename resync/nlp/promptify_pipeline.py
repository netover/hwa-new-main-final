"""Utilities for extracting structured fields from TWS/HWA logs using
Promptify.

This module defines a simple wrapper around the Promptify library to
facilitate extraction of key fields from free‑form log messages.  It
builds on a Jinja template (``resync/prompts/log_ner.jinja``) and returns
Python dictionaries rather than raw text.  When no API key is
configured the extractor will raise a ``RuntimeError`` on construction.

If you need stricter validation of the returned JSON, consider using
the optional Instructor library together with a Pydantic model.
"""

from __future__ import annotations

from typing import Any, Dict
import os

try:
    # The Promptify library provides a high‑level API for applying
    # templated prompts to large language models and returning
    # structured outputs.  Installation is optional; if unavailable
    # at runtime this module will still import but the extractor
    # cannot be instantiated.
    from promptify import Prompter
    from promptify import OpenAI
    from promptify.pipeline import Pipeline
except Exception:
    # Fall back to None if Promptify is not installed.  This allows
    # tests to monkeypatch the extractor class without requiring the
    # library to be installed at import time.
    Prompter = None  # type: ignore[assignment]
    OpenAI = None  # type: ignore[assignment]
    Pipeline = None  # type: ignore[assignment]

TWS_LABELS = ["job_id", "workstation", "status", "timestamp", "root_cause"]


class LogFieldExtractor:
    """High level wrapper around Promptify for log field extraction."""

    def __init__(self, template_path: str = "resync/prompts/log_ner.jinja") -> None:
        if Prompter is None or OpenAI is None or Pipeline is None:
            raise RuntimeError(
                "Promptify library is not installed; please install promptify to "
                "enable NLP log extraction."
            )
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY ausente para Promptify.")
        # Initialise the model and prompter.  You can substitute other
        # providers here if your environment supports them.
        self.model = OpenAI(api_key=api_key)
        self.prompter = Prompter(self.model, template=template_path)
        self.pipeline = Pipeline(self.prompter)

    async def extract(self, text: str) -> Dict[str, Any]:
        """Execute the prompt on the given text and return a dictionary.

        The extractor runs synchronously under the hood because
        Promptify's ``Pipeline.run`` method is synchronous.  Should
        future versions support async execution this method can be
        adjusted accordingly.
        """
        # Run the pipeline.  The return type is expected to be a
        # dictionary with keys matching those defined in the Jinja
        # template.  If the output is not a dict we return an empty
        # structure.
        result: Any = self.pipeline.run(text=text)
        out: Dict[str, Any] = {
            key: result.get(key) if isinstance(result, dict) else None
            for key in TWS_LABELS
        }
        # Normalise the status field into our known domain.
        if out.get("status"):
            status = str(out["status"]).upper()
            out["status"] = status if status in {"SUCC", "ABEND", "RUNNING", "HOLD"} else None
        return out