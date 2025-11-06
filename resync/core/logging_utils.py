"""Logging utilities for the Resync application."""

import re
import logging
from typing import Any, Dict


class SecretRedactor(logging.Filter):
    """
    A logging filter that redacts sensitive information from log records.

    This filter will redact fields containing sensitive data like passwords,
    API keys, tokens, etc. from log messages and structured log data.
    """

    def __init__(self, name: str = ""):
        """
        Initialize the SecretRedactor filter.

        Args:
            name: Optional name for the filter
        """
        super().__init__(name)
        # Define patterns for sensitive field names
        self.sensitive_patterns = {
            "password",
            "token",
            "secret",
            "api_key",
            "apikey",
            "authorization",
            "auth",
            "credential",
            "private_key",
            "access_token",
            "refresh_token",
            "client_secret",
            "pin",
            "cvv",
            "ssn",
            "credit_card",
            "card_number",
            "tws_password",
            "neo4j_password",
            "llm_api_key",
        }

        # Define regex patterns for sensitive values
        self.sensitive_value_patterns = [
            # Basic patterns for key=value structures
            r'(?:password|pwd|token|secret|key|api_key)\s*[:=]\s*["\'][^"\']*["\']',
            r"(?:authorization)[:\s]*bearer\s+[^\s]+",
            r"(?:basic)\s+[a-zA-Z0-9+/=]+",
            # Credit card pattern
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            # SSN pattern
            r"\b\d{3}-?\d{2}-?\d{4}\b",
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter the log record, redacting sensitive information.

        Args:
            record: The log record to filter

        Returns:
            Always True to ensure the record is not filtered out
        """
        # Redact from the message
        record.msg = self._redact_sensitive_data(str(record.msg))

        # If the record has an args attribute, redact from there too
        if record.args:
            record.args = self._redact_args(record.args)

        # If the record has additional structured data, redact from there
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if isinstance(value, str):
                    record.__dict__[key] = self._redact_sensitive_data(value)
                elif isinstance(value, dict):
                    record.__dict__[key] = self._redact_dict(value)

        return True

    def _redact_args(self, args: Any) -> Any:
        """
        Redact sensitive data from log record args.

        Args:
            args: The arguments to redact

        Returns:
            The redacted arguments
        """
        if isinstance(args, (list, tuple)):
            redacted_args = []
            for arg in args:
                if isinstance(arg, str):
                    redacted_args.append(self._redact_sensitive_data(arg))
                elif isinstance(arg, dict):
                    redacted_args.append(self._redact_dict(arg))
                else:
                    redacted_args.append(arg)
            return redacted_args if isinstance(args, list) else tuple(redacted_args)
        elif isinstance(args, dict):
            return self._redact_dict(args)
        else:
            return args

    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redact sensitive data from a dictionary.

        Args:
            data: The dictionary to redact

        Returns:
            The redacted dictionary
        """
        if not isinstance(data, dict):
            return data

        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            # Check if key matches sensitive patterns
            if any(sensitive in key_lower for sensitive in self.sensitive_patterns):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item)
                    if isinstance(item, dict)
                    else self._redact_sensitive_data(str(item))
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                redacted[key] = self._redact_sensitive_data(value)
            else:
                redacted[key] = value
        return redacted

    def _redact_sensitive_data(self, data: str) -> str:
        """
        Redact sensitive data from a string.

        Args:
            data: The string to redact

        Returns:
            The redacted string
        """
        if not isinstance(data, str):
            return data

        redacted = data
        for pattern in self.sensitive_value_patterns:
            redacted = re.sub(pattern, "***REDACTED***", redacted, flags=re.IGNORECASE)
        return redacted
