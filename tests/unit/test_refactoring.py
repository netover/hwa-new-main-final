"""
Unit tests for refactored components using Strategy, Factory, and Command patterns.

This module contains comprehensive unit tests for the refactored components
that were previously complex functions with high cyclomatic complexity.
"""

import unittest

from resync.core.exceptions import (
    DatabaseError,
    LLMError,
    NotFoundError,
    TWSConnectionError,
)
from resync.core.exceptions import (
    ResyncException as BaseResyncException,
)
from resync.core.exceptions_enhanced import (
    ResyncException as EnhancedResyncException,
)
from resync.core.utils.error_factories import (
    BaseResyncExceptionFactory,
    DatabaseExceptionFactory,
    EnhancedResyncExceptionFactory,
    ErrorFactory,
    LLMExceptionFactory,
    NotFoundExceptionHandler,
    TWSConnectionExceptionFactory,
    UnknownExceptionFactory,
)
from resync.core.utils.error_utils import ErrorResponseBuilder
from resync.core.utils.json_commands import (
    JSONParseCommand,
    JSONParseCommandExecutor,
    JSONParseCommandFactory,
)
from resync.core.utils.llm_factories import (
    AnthropicProvider,
    DefaultLLMProvider,
    LLMFactory,
    LLMProvider,
    LLMProviderFactory,
    OllamaProvider,
    OpenAIProvider,
)
from resync.models.error_models import (
    BusinessLogicErrorResponse,
    ExternalServiceErrorResponse,
    SystemErrorResponse,
    ValidationErrorResponse,
)


class TestErrorFactories(unittest.TestCase):
    """Test cases for error response factories."""

    def setUp(self):
        """Set up test fixtures."""
        self.builder = ErrorResponseBuilder()

    def test_enhanced_resync_exception_factory(self):
        """Test enhanced Resync exception factory."""
        exception = EnhancedResyncException(
            message="Test error",
            user_friendly_message="Test user message",
            error_category="VALIDATION",
            details={}
        )

        response = EnhancedResyncExceptionFactory.create_response(self.builder, exception, False)

        self.assertIsInstance(response, ValidationErrorResponse)
        self.assertEqual(response.message, "Test user message")

    def test_tws_connection_exception_factory(self):
        """Test TWS connection exception factory."""
        exception = TWSConnectionError("Connection failed")

        response = TWSConnectionExceptionFactory.create_response(self.builder, exception, False)

        self.assertIsInstance(response, ExternalServiceErrorResponse)
        self.assertEqual(response.error_code, "EXTERNAL_SERVICE_ERROR")

    def test_llm_exception_factory(self):
        """Test LLM exception factory."""
        exception = LLMError("LLM error")

        response = LLMExceptionFactory.create_response(self.builder, exception, False)

        self.assertIsInstance(response, ExternalServiceErrorResponse)
        self.assertEqual(response.error_code, "EXTERNAL_SERVICE_ERROR")

    def test_database_exception_factory(self):
        """Test database exception factory."""
        exception = DatabaseError("Database error")

        response = DatabaseExceptionFactory.create_response(self.builder, exception, False)

        self.assertIsInstance(response, SystemErrorResponse)
        self.assertEqual(response.error_code, "SYSTEM_ERROR")

    def test_not_found_exception_factory(self):
        """Test not found exception factory."""
        exception = NotFoundError("Resource not found")

        response = NotFoundExceptionHandler.create_response(self.builder, exception, False)

        self.assertIsInstance(response, BusinessLogicErrorResponse)
        self.assertEqual(response.error_code, "BUSINESS_LOGIC_ERROR")

    def test_base_resync_exception_factory(self):
        """Test base Resync exception factory."""
        exception = BaseResyncException("Base error")

        response = BaseResyncExceptionFactory.create_response(self.builder, exception, False)

        self.assertIsInstance(response, SystemErrorResponse)
        self.assertEqual(response.error_code, "SYSTEM_ERROR")

    def test_unknown_exception_factory(self):
        """Test unknown exception factory."""
        exception = Exception("Unknown error")

        response = UnknownExceptionFactory.create_response(self.builder, exception, False)

        self.assertIsInstance(response, SystemErrorResponse)
        self.assertEqual(response.error_code, "SYSTEM_ERROR")

    def test_error_factory(self):
        """Test error factory."""
        exception = EnhancedResyncException(
            message="Test error",
            user_friendly_message="Test user message",
            error_category="VALIDATION",
            details={}
        )

        response = ErrorFactory.create_error_response(exception)

        self.assertIsInstance(response, ValidationErrorResponse)
        self.assertEqual(response.message, "Test user message")


class TestJSONCommands(unittest.TestCase):
    """Test cases for JSON parsing commands."""

    def test_json_parse_command_valid(self):
        """Test JSON parse command with valid input."""
        text = '{"key1": "value1", "key2": "value2"}'
        required_keys = ["key1", "key2"]

        command = JSONParseCommand(text, required_keys)
        result = command.execute()

        self.assertEqual(result["key1"], "value1")
        self.assertEqual(result["key2"], "value2")

    def test_json_parse_command_missing_key(self):
        """Test JSON parse command with missing required key."""
        text = '{"key1": "value1"}'
        required_keys = ["key1", "key2"]

        command = JSONParseCommand(text, required_keys)

        with self.assertRaises(ParsingError):
            command.execute()

    def test_json_parse_command_strict_mode_extra_key(self):
        """Test JSON parse command with extra key in strict mode."""
        text = '{"key1": "value1", "key2": "value2", "key3": "value3"}'
        required_keys = ["key1", "key2"]

        command = JSONParseCommand(text, required_keys, strict=True)

        with self.assertRaises(ParsingError):
            command.execute()

    def test_json_parse_command_non_strict_mode_extra_key(self):
        """Test JSON parse command with extra key in non-strict mode."""
        text = '{"key1": "value1", "key2": "value2", "key3": "value3"}'
        required_keys = ["key1", "key2"]

        command = JSONParseCommand(text, required_keys, strict=False)
        result = command.execute()

        self.assertEqual(result["key1"], "value1")
        self.assertEqual(result["key2"], "value2")
        self.assertEqual(result["key3"], "value3")

    def test_json_parse_command_invalid_json(self):
        """Test JSON parse command with invalid JSON."""
        text = '{"key1": "value1", "key2":}'
        required_keys = ["key1", "key2"]

        command = JSONParseCommand(text, required_keys)

        with self.assertRaises(ParsingError):
            command.execute()

    def test_json_parse_command_no_json(self):
        """Test JSON parse command with no JSON object."""
        text = 'This is not JSON'
        required_keys = ["key1", "key2"]

        command = JSONParseCommand(text, required_keys)

        with self.assertRaises(ParsingError):
            command.execute()

    def test_json_parse_command_factory(self):
        """Test JSON parse command factory."""
        text = '{"key1": "value1", "key2": "value2"}'
        required_keys = ["key1", "key2"]

        command = JSONParseCommandFactory.create_command(text, required_keys)

        self.assertIsInstance(command, JSONParseCommand)

    def test_json_parse_command_executor(self):
        """Test JSON parse command executor."""
        text = '{"key1": "value1", "key2": "value2"}'
        required_keys = ["key1", "key2"]

        result = JSONParseCommandExecutor.execute_command(text, required_keys)

        self.assertEqual(result["key1"], "value1")
        self.assertEqual(result["key2"], "value2")


class TestLLMFactories(unittest.TestCase):
    """Test cases for LLM factories."""

    def test_llm_factory(self):
        """Test LLM factory."""
        # This is a complex function that would normally require mocking
        # For now, we'll just test that it returns a string
        result = LLMFactory.call_llm(
            prompt="Test prompt",
            model="gpt-4o",
            max_tokens=100,
            temperature=0.1
        )

        # Since we're not mocking the actual LLM call, we'll get a mock response
        self.assertIsInstance(result, str)
        self.assertEqual(result, "LLM service is currently unavailable. This is a mock response for development purposes.")

    def test_llm_provider_factory(self):
        """Test LLM provider factory."""
        provider = LLMProviderFactory.create_provider("openai", model="gpt-4o")
        self.assertIsInstance(provider, OpenAIProvider)

        provider = LLMProviderFactory.create_provider("ollama", model="mistral")
        self.assertIsInstance(provider, OllamaProvider)

        provider = LLMProviderFactory.create_provider("anthropic", model="claude-3-opus-20240229")
        self.assertIsInstance(provider, AnthropicProvider)

        provider = LLMProviderFactory.create_provider("unknown", model="gpt-4o")
        self.assertIsInstance(provider, DefaultLLMProvider)

    def test_llm_provider_base(self):
        """Test LLM provider base class."""
        provider = LLMProvider(model="gpt-4o")
        self.assertEqual(provider.model, "gpt-4o")

    def test_openai_provider(self):
        """Test OpenAI provider."""
        provider = OpenAIProvider(model="gpt-4o")
        self.assertEqual(provider.model, "gpt-4o")
        self.assertEqual(provider.api_base, "https://api.openai.com/v1")

    def test_ollama_provider(self):
        """Test Ollama provider."""
        provider = OllamaProvider(model="mistral")
        self.assertEqual(provider.model, "mistral")
        self.assertEqual(provider.api_base, "http://localhost:11434/v1")

    def test_anthropic_provider(self):
        """Test Anthropic provider."""
        provider = AnthropicProvider(model="claude-3-opus-20240229")
        self.assertEqual(provider.model, "claude-3-opus-20240229")
        self.assertEqual(provider.api_base, "https://api.anthropic.com/v1")

    def test_default_llm_provider(self):
        """Test default LLM provider."""
        provider = DefaultLLMProvider(model="gpt-4o")
        self.assertEqual(provider.model, "gpt-4o")
        self.assertEqual(provider.api_base, None)


if __name__ == '__main__':
    unittest.main()




