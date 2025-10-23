"""
Unit tests for refactored components using Strategy, Factory, and Command patterns.

This module contains comprehensive unit tests for the refactored components
that were previously complex functions with high cyclomatic complexity.
"""

import asyncio
import json
import unittest
from typing import Any, Dict, List

from resync.core.compliance.report_strategies import (
    ControlComplianceStrategy,
    CriteriaScoresStrategy,
    OverallComplianceStrategy,
    ControlStatusSummaryStrategy,
    EvidenceSummaryStrategy,
    AvailabilitySummaryStrategy,
    ProcessingIntegritySummaryStrategy,
    ConfidentialityIncidentsSummaryStrategy,
    RecommendationsStrategy,
    ReportGenerator
)
from resync.core.utils.error_factories import (
    ErrorFactory,
    EnhancedResyncExceptionFactory,
    TWSConnectionExceptionFactory,
    LLMExceptionFactory,
    DatabaseExceptionFactory,
    NotFoundExceptionHandler,
    BaseResyncExceptionFactory,
    UnknownExceptionFactory
)
from resync.core.utils.json_commands import (
    JSONParseCommand,
    JSONParseCommandFactory,
    JSONParseCommandExecutor
)
from resync.core.utils.llm_factories import (
    LLMFactory,
    LLMProviderFactory,
    LLMProvider,
    OpenAIProvider,
    OllamaProvider,
    AnthropicProvider,
    DefaultLLMProvider
)
from resync.models.error_models import (
    AuthenticationErrorResponse,
    AuthorizationErrorResponse,
    BaseErrorResponse,
    BusinessLogicErrorResponse,
    ErrorCategory,
    ErrorSeverity,
    ExternalServiceErrorResponse,
    RateLimitErrorResponse,
    SystemErrorResponse,
    ValidationErrorResponse,
)
from resync.core.exceptions import (
    DatabaseError,
    LLMError,
    NotFoundError,
    ResyncException as BaseResyncException,
    TWSConnectionError,
)
from resync.core.exceptions_enhanced import (
    DatabaseError as EnhancedDatabaseError,
    LLMError as EnhancedLLMError,
    NotFoundError as EnhancedNotFoundError,
    ResyncException as EnhancedResyncException,
    TWSConnectionError as EnhancedTWSConnectionError,
)
from resync.core.soc2_compliance_refactored import (
    SOC2ComplianceManager,
    SOC2Control,
    SOC2Evidence,
    AvailabilityMetric,
    ProcessingIntegrityCheck,
    ConfidentialityIncident,
    SOC2ComplianceConfig,
    SOC2TrustServiceCriteria,
    ControlCategory,
    ControlStatus
)
from resync.core.utils.error_utils import ErrorResponseBuilder
from resync.settings import settings


class TestReportStrategies(unittest.TestCase):
    """Test cases for report generation strategies."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = SOC2ComplianceManager()
        
        # Add some test controls
        control = SOC2Control(
            control_id="TEST-001",
            name="Test Control",
            description="Test control for reporting",
            category=ControlCategory.ACCESS_CONTROL,
            criteria=[SOC2TrustServiceCriteria.SECURITY],
            status=ControlStatus.COMPLIANT
        )
        self.manager.controls[control.control_id] = control
        
        # Add some test evidence
        evidence = SOC2Evidence(
            evidence_id="evidence-001",
            control_id="TEST-001",
            evidence_type="document",
            description="Test evidence",
            collected_at=time.time(),
            validity_days=365
        )
        self.manager.evidence[evidence.evidence_id] = evidence
        
        # Add some test metrics
        metric = AvailabilityMetric(
            uptime_percentage=99.95,
            response_time_avg=0.15,
            error_rate=0.001
        )
        self.manager.availability_metrics.append(metric)
        
        # Add some test integrity checks
        integrity_check = ProcessingIntegrityCheck(
            check_id="check-001",
            operation_type="batch_processing",
            records_processed=1000,
            records_failed=0,
            processing_time=2.5
        )
        self.manager.processing_checks.append(integrity_check)
        
        # Add some test incidents
        incident = ConfidentialityIncident(
            incident_id="incident-001",
            data_category="PII",
            breach_type="unauthorized_access",
            affected_records=10,
            severity="high",
            detected_by="automated",
            resolved=False
        )
        self.manager.confidentiality_incidents.append(incident)
    
    def test_control_compliance_strategy(self):
        """Test control compliance strategy."""
        strategy = ControlComplianceStrategy()
        result = strategy.execute(self.manager)
        
        self.assertEqual(result["total_controls"], 1)
        self.assertEqual(result["compliant_controls"], 1)
        self.assertEqual(result["compliance_rate"], 1.0)
    
    def test_criteria_scores_strategy(self):
        """Test criteria scores strategy."""
        strategy = CriteriaScoresStrategy()
        result = strategy.execute(self.manager)
        
        self.assertIn("security", result)
        self.assertEqual(result["security"]["score"], 1.0)
        self.assertEqual(result["security"]["compliant_controls"], 1)
        self.assertEqual(result["security"]["total_controls"], 1)
    
    def test_overall_compliance_strategy(self):
        """Test overall compliance strategy."""
        strategy = OverallComplianceStrategy()
        result = strategy.execute(self.manager)
        
        self.assertEqual(result, 1.0)
    
    def test_control_status_summary_strategy(self):
        """Test control status summary strategy."""
        strategy = ControlStatusSummaryStrategy()
        result = strategy.execute(self.manager)
        
        self.assertIn("compliant", result)
        self.assertEqual(result["compliant"], 1)
    
    def test_evidence_summary_strategy(self):
        """Test evidence summary strategy."""
        strategy = EvidenceSummaryStrategy()
        result = strategy.execute(self.manager)
        
        self.assertEqual(result["total_valid_evidence"], 1)
        self.assertIn("document", result["by_type"])
        self.assertEqual(result["by_type"]["document"], 1)
    
    def test_availability_summary_strategy(self):
        """Test availability summary strategy."""
        strategy = AvailabilitySummaryStrategy()
        result = strategy.execute(self.manager)
        
        self.assertEqual(result["average_availability"], 99.95)
        self.assertEqual(result["target_availability"], 99.9)
        self.assertTrue(result["meets_target"])
    
    def test_processing_integrity_summary_strategy(self):
        """Test processing integrity summary strategy."""
        strategy = ProcessingIntegritySummaryStrategy()
        result = strategy.execute(self.manager)
        
        self.assertEqual(result["average_integrity_score"], 100.0)
        self.assertEqual(result["failed_checks"], 0)
        self.assertEqual(result["total_checks"], 1)
        self.assertTrue(result["meets_target"])
    
    def test_confidentiality_incidents_summary_strategy(self):
        """Test confidentiality incidents summary strategy."""
        strategy = ConfidentialityIncidentsSummaryStrategy()
        result = strategy.execute(self.manager)
        
        self.assertEqual(result["total_incidents"], 1)
        self.assertIn("high", result["by_severity"])
        self.assertEqual(result["by_severity"]["high"], 1)
        self.assertEqual(result["unresolved_incidents"], 1)
    
    def test_recommendations_strategy(self):
        """Test recommendations strategy."""
        strategy = RecommendationsStrategy()
        result = strategy.execute(self.manager)
        
        # Since we have a compliant system, no recommendations should be generated
        self.assertEqual(len(result), 0)
    
    def test_report_generator(self):
        """Test report generator."""
        generator = ReportGenerator()
        report = generator.generate_report(self.manager)
        
        self.assertIn("overall_compliance_score", report)
        self.assertEqual(report["overall_compliance_score"], 1.0)
        self.assertIn("criteria_scores", report)
        self.assertIn("control_status", report)
        self.assertIn("evidence_summary", report)
        self.assertIn("availability_summary", report)
        self.assertIn("processing_integrity_summary", report)
        self.assertIn("confidentiality_incidents", report)
        self.assertIn("recommendations", report)


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