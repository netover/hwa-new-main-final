"""Módulo para funções de segurança e validação de input."""

import logging
import os
import re
from typing import Annotated, Any, Type

from fastapi import Path

# Expressão regular para permitir caracteres alfanuméricos, espaços, e pontuação comum.
# Isso ajuda a prevenir a injeção de caracteres de controle ou scripts complexos.
SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9\s.,!?'\"()\-:;]*$")


class InputSanitizer:
    """
    Class for sanitizing and validating user inputs.
    Provides methods for cleaning various types of input data.
    """

    @staticmethod
    def sanitize_environment_value(
        env_var_name: str, default_value: Any, value_type: Type = str
    ) -> Any:
        """
        Sanitize and validate environment variable values.

        Args:
            env_var_name: Name of the environment variable
            default_value: Default value if env var is not set or invalid
            value_type: Expected type of the value (str, int, float, bool)

        Returns:
            Sanitized value of the specified type
        """
        raw_value = os.getenv(env_var_name, default_value)

        try:
            if value_type == str:
                return str(raw_value)
            elif value_type == int:
                return int(raw_value)
            elif value_type == float:
                return float(raw_value)
            elif value_type == bool:
                # Handle boolean conversion from string
                if isinstance(raw_value, str):
                    return raw_value.lower() in ("true", "1", "yes", "on")
                return bool(raw_value)
            else:
                # For other types, try to convert using the type constructor
                return value_type(raw_value)
        except (ValueError, TypeError):
            # If conversion fails, return the default value
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Invalid value for environment variable {env_var_name}: {raw_value}. Using default: {default_value}"
            )
            return default_value

    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """
        Remove caracteres potencialmente perigosos de uma string de entrada.
        Esta é uma camada de defesa básica e deve ser adaptada conforme a necessidade.

        Args:
            text: A string de entrada do usuário.
            max_length: Maximum length allowed for the string.

        Returns:
            A string sanitizada.
        """
        if not text:
            return ""

        # Truncate to max length
        text = text[:max_length]

        # Exemplo simples: remove tudo que não corresponder ao padrão seguro.
        # Em um cenário real, pode-se usar bibliotecas como `bleach` para sanitizar HTML.
        sanitized_text = "".join(SAFE_STRING_PATTERN.findall(text))
        return sanitized_text

    @staticmethod
    def sanitize_dict(data: dict, max_depth: int = 3, current_depth: int = 0) -> dict:
        """
        Recursively sanitize a dictionary.

        Args:
            data: Dictionary to sanitize
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth

        Returns:
            Sanitized dictionary
        """
        if current_depth >= max_depth:
            return {}

        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            clean_key = InputSanitizer.sanitize_string(str(key), 100)

            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[clean_key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[clean_key] = InputSanitizer.sanitize_dict(
                    value, max_depth, current_depth + 1
                )
            elif isinstance(value, list):
                sanitized[clean_key] = InputSanitizer.sanitize_list(
                    value, max_depth, current_depth + 1
                )
            elif isinstance(value, (int, float, bool)):
                sanitized[clean_key] = value
            else:
                # Convert other types to string and sanitize
                sanitized[clean_key] = InputSanitizer.sanitize_string(str(value))

        return sanitized

    @staticmethod
    def sanitize_list(data: list, max_depth: int = 3, current_depth: int = 0) -> list:
        """
        Recursively sanitize a list.

        Args:
            data: List to sanitize
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth

        Returns:
            Sanitized list
        """
        if current_depth >= max_depth:
            return []

        sanitized = []
        for item in data:
            if isinstance(item, str):
                sanitized.append(InputSanitizer.sanitize_string(item))
            elif isinstance(item, dict):
                sanitized.append(
                    InputSanitizer.sanitize_dict(item, max_depth, current_depth + 1)
                )
            elif isinstance(item, list):
                sanitized.append(
                    InputSanitizer.sanitize_list(item, max_depth, current_depth + 1)
                )
            elif isinstance(item, (int, float, bool)):
                sanitized.append(item)
            else:
                # Convert other types to string and sanitize
                sanitized.append(InputSanitizer.sanitize_string(str(item)))

        return sanitized


def sanitize_input(text: str) -> str:
    """
    Remove caracteres potencialmente perigosos de uma string de entrada.
    Esta é uma camada de defesa básica e deve ser adaptada conforme a necessidade.

    Args:
        text: A string de entrada do usuário.

    Returns:
        A string sanitizada.
    """
    # Exemplo simples: remove tudo que não corresponder ao padrão seguro.
    # Em um cenário real, pode-se usar bibliotecas como `bleach` para sanitizar HTML.
    sanitized_text = "".join(SAFE_STRING_PATTERN.findall(text))
    return sanitized_text


# Tipo anotado para IDs, garantindo que eles sigam um formato seguro.
SafeAgentID = Annotated[
    str, Path(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
]
