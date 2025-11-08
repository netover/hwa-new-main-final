"""
Tests for Health Checker Factory

This module contains unit tests for the HealthCheckerFactory class.
"""

from unittest.mock import MagicMock, patch

from resync.core.health.health_checkers.base_health_checker import BaseHealthChecker
from resync.core.health.health_checkers.health_checker_factory import HealthCheckerFactory
from resync.core.health_models import ComponentType, HealthCheckConfig


class MockHealthChecker(BaseHealthChecker):
    """Mock health checker for testing."""

    @property
    def component_name(self) -> str:
        return "mock"

    @property
    def component_type(self) -> ComponentType:
        return ComponentType.OTHER

    async def check_health(self):
        return MagicMock()


class TestHealthCheckerFactory:
    """Test cases for HealthCheckerFactory."""

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        factory = HealthCheckerFactory()
        assert factory.config is not None
        assert len(factory._checkers) > 0
        assert len(factory._checker_classes) > 0

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = HealthCheckConfig(timeout_seconds=60)
        factory = HealthCheckerFactory(config)
        assert factory.config == config

    def test_get_health_checker(self):
        """Test getting a health checker by name."""
        factory = HealthCheckerFactory()
        checker = factory.get_health_checker("database")
        assert checker is not None
        assert checker.component_name == "database"

    def test_get_health_checker_nonexistent(self):
        """Test getting a non-existent health checker."""
        factory = HealthCheckerFactory()
        checker = factory.get_health_checker("nonexistent")
        assert checker is None

    def test_get_all_health_checkers(self):
        """Test getting all health checkers."""
        factory = HealthCheckerFactory()
        checkers = factory.get_all_health_checkers()
        assert isinstance(checkers, dict)
        assert len(checkers) > 0
        assert "database" in checkers
        assert "redis" in checkers

    def test_get_enabled_health_checkers(self):
        """Test getting enabled health checkers."""
        factory = HealthCheckerFactory()
        enabled_checkers = factory.get_enabled_health_checkers()
        assert isinstance(enabled_checkers, dict)
        assert len(enabled_checkers) > 0

    def test_get_health_checker_names(self):
        """Test getting health checker names."""
        factory = HealthCheckerFactory()
        names = factory.get_health_checker_names()
        assert isinstance(names, list)
        assert len(names) > 0
        assert "database" in names
        assert "redis" in names

    def test_get_enabled_health_checker_names(self):
        """Test getting enabled health checker names."""
        factory = HealthCheckerFactory()
        names = factory.get_enabled_health_checker_names()
        assert isinstance(names, list)
        assert len(names) > 0

    def test_register_health_checker(self):
        """Test registering a new health checker."""
        factory = HealthCheckerFactory()

        initial_count = len(factory._checker_classes)
        factory.register_health_checker("test_component", MockHealthChecker)

        assert len(factory._checker_classes) == initial_count + 1
        assert "test_component" in factory._checker_classes
        assert factory.get_health_checker("test_component") is not None

    def test_unregister_health_checker(self):
        """Test unregistering a health checker."""
        factory = HealthCheckerFactory()

        # Register first
        factory.register_health_checker("test_component", MockHealthChecker)
        assert "test_component" in factory._checker_classes

        # Unregister
        factory.unregister_health_checker("test_component")
        assert "test_component" not in factory._checker_classes
        assert factory.get_health_checker("test_component") is None

    def test_unregister_nonexistent_health_checker(self):
        """Test unregistering a non-existent health checker."""
        factory = HealthCheckerFactory()

        # Should not raise an exception
        factory.unregister_health_checker("nonexistent")
        assert len(factory._checker_classes) == len(factory._checker_classes)  # No change

    def test_validate_all_checkers(self):
        """Test validating all health checkers."""
        factory = HealthCheckerFactory()
        validation_results = factory.validate_all_checkers()

        assert isinstance(validation_results, dict)
        assert len(validation_results) > 0

        # Each checker should have a validation result (list)
        for _checker_name, errors in validation_results.items():
            assert isinstance(errors, list)

    def test_get_component_type_mapping(self):
        """Test getting component type mapping."""
        factory = HealthCheckerFactory()
        mapping = factory.get_component_type_mapping()

        assert isinstance(mapping, dict)
        assert len(mapping) > 0
        assert "database" in mapping
        assert "redis" in mapping

        # Check that mappings are correct
        assert mapping["database"] == ComponentType.DATABASE
        assert mapping["redis"] == ComponentType.REDIS

    def test_is_component_enabled(self):
        """Test checking if component is enabled."""
        factory = HealthCheckerFactory()

        # Test enabled components
        assert factory._is_component_enabled("database") is True
        assert factory._is_component_enabled("redis") is True

        # Test disabled component
        assert factory._is_component_enabled("nonexistent") is False

    @patch('resync.core.health.health_checkers.health_checker_factory.DatabaseHealthChecker')
    def test_factory_initializes_all_checkers(self, mock_db_checker):
        """Test that factory initializes all checker instances."""
        factory = HealthCheckerFactory()

        # Check that all expected checkers are initialized
        expected_checkers = [
            "database", "redis", "cache_hierarchy", "file_system",
            "memory", "cpu", "tws_monitor", "connection_pools", "websocket_pool"
        ]

        for checker_name in expected_checkers:
            assert checker_name in factory._checkers
            assert factory._checkers[checker_name] is not None
