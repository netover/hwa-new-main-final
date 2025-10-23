"""
Tests for Base Health Checker

This module contains unit tests for the BaseHealthChecker class.
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.health_models import ComponentType, HealthCheckConfig, HealthStatus
from resync.core.health.health_checkers.base_health_checker import BaseHealthChecker


class ConcreteHealthChecker(BaseHealthChecker):
    """Concrete implementation of BaseHealthChecker for testing."""

    @property
    def component_name(self) -> str:
        return "test_component"

    @property
    def component_type(self) -> ComponentType:
        return ComponentType.OTHER

    async def check_health(self):
        """Mock health check implementation."""
        return MagicMock()


class TestBaseHealthChecker:
    """Test cases for BaseHealthChecker."""

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        checker = ConcreteHealthChecker()
        assert checker.config is not None
        assert isinstance(checker.config, HealthCheckConfig)
        assert checker.logger is not None

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = HealthCheckConfig(timeout_seconds=60)
        checker = ConcreteHealthChecker(config)
        assert checker.config == config
        assert checker.config.timeout_seconds == 60

    def test_component_properties(self):
        """Test component name and type properties."""
        checker = ConcreteHealthChecker()
        assert checker.component_name == "test_component"
        assert checker.component_type == ComponentType.OTHER

    @pytest.mark.asyncio
    async def test_check_health_with_timeout_success(self):
        """Test successful health check with timeout."""
        checker = ConcreteHealthChecker()

        # Mock the check_health method to return a successful result
        mock_health = MagicMock()
        mock_health.response_time_ms = None
        checker.check_health = AsyncMock(return_value=mock_health)

        result = await checker.check_health_with_timeout(timeout_seconds=30)

        assert result == mock_health
        assert result.response_time_ms is not None
        checker.check_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_with_timeout_exception(self):
        """Test health check with timeout when exception occurs."""
        checker = ConcreteHealthChecker()

        # Mock the check_health method to raise an exception
        test_exception = Exception("Test error")
        checker.check_health = AsyncMock(side_effect=test_exception)

        result = await checker.check_health_with_timeout(timeout_seconds=30)

        assert result.status == ComponentType.UNKNOWN  # Default for exceptions
        assert "Test error" in result.message
        assert result.error_count == 1
        assert result.last_check is not None

    @pytest.mark.asyncio
    async def test_check_health_with_timeout_timeout_error(self):
        """Test health check timeout handling."""
        checker = ConcreteHealthChecker()

        # Mock the check_health method to sleep longer than timeout
        async def slow_check():
            await asyncio.sleep(2)
            return MagicMock()

        checker.check_health = slow_check

        result = await checker.check_health_with_timeout(timeout_seconds=0.1)

        # Should handle timeout gracefully
        assert result is not None
        assert result.last_check is not None

    def test_get_component_config(self):
        """Test getting component-specific configuration."""
        checker = ConcreteHealthChecker()
        config = checker.get_component_config()

        assert isinstance(config, dict)
        assert "timeout_seconds" in config
        assert "retry_attempts" in config

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        checker = ConcreteHealthChecker()
        errors = checker.validate_config()

        # Should have no errors for default config
        assert isinstance(errors, list)

    def test_validate_config_invalid_timeout(self):
        """Test configuration validation with invalid timeout."""
        config = HealthCheckConfig(timeout_seconds=-1)
        checker = ConcreteHealthChecker(config)

        errors = checker.validate_config()
        assert len(errors) > 0
        assert any("timeout_seconds" in error for error in errors)

    def test_get_status_for_exception_default(self):
        """Test default exception status mapping."""
        checker = ConcreteHealthChecker()
        exception = Exception("Test error")

        status = checker._get_status_for_exception(exception)
        assert status == ComponentType.UNKNOWN