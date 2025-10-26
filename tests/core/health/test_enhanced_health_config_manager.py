"""
Tests for Enhanced Health Configuration Manager

This module contains unit tests for the EnhancedHealthConfigurationManager class.
"""

import os
from unittest.mock import MagicMock


from resync.core.health_models import HealthCheckConfig
from resync.core.health.enhanced_health_config_manager import EnhancedHealthConfigurationManager
from resync.core.health.health_checkers.health_checker_factory import HealthCheckerFactory


class TestEnhancedHealthConfigurationManager:
    """Test cases for EnhancedHealthConfigurationManager."""

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        config_manager = EnhancedHealthConfigurationManager()
        assert config_manager.config is not None
        assert config_manager._checker_factory is None

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = HealthCheckConfig(timeout_seconds=60)
        config_manager = EnhancedHealthConfigurationManager(config)
        assert config_manager.config == config

    def test_set_health_checker_factory(self):
        """Test setting health checker factory."""
        config_manager = EnhancedHealthConfigurationManager()
        factory = HealthCheckerFactory()

        config_manager.set_health_checker_factory(factory)
        assert config_manager._checker_factory == factory

    def test_get_checker_specific_config_without_factory(self):
        """Test getting checker-specific config without factory."""
        config_manager = EnhancedHealthConfigurationManager()

        # Should fallback to parent implementation
        config = config_manager.get_checker_specific_config("database")
        assert isinstance(config, dict)
        assert "timeout_seconds" in config

    def test_get_checker_specific_config_with_factory(self):
        """Test getting checker-specific config with factory."""
        config_manager = EnhancedHealthConfigurationManager()
        factory = HealthCheckerFactory()
        config_manager.set_health_checker_factory(factory)

        # Mock checker to return specific config
        mock_checker = MagicMock()
        mock_checker.get_component_config.return_value = {"custom_timeout": 45}
        factory.get_health_checker = MagicMock(return_value=mock_checker)

        config = config_manager.get_checker_specific_config("database")
        assert isinstance(config, dict)

    def test_validate_all_checkers_config_without_factory(self):
        """Test validating all checkers config without factory."""
        config_manager = EnhancedHealthConfigurationManager()
        validation = config_manager.validate_all_checkers_config()
        assert validation == {}  # Empty dict when no factory

    def test_validate_all_checkers_config_with_factory(self):
        """Test validating all checkers config with factory."""
        config_manager = EnhancedHealthConfigurationManager()
        factory = HealthCheckerFactory()
        config_manager.set_health_checker_factory(factory)

        validation = config_manager.validate_all_checkers_config()
        assert isinstance(validation, dict)
        assert len(validation) > 0

    def test_get_component_thresholds_enhanced(self):
        """Test getting enhanced component thresholds."""
        config_manager = EnhancedHealthConfigurationManager()

        thresholds = config_manager.get_component_thresholds_enhanced("database")
        assert isinstance(thresholds, dict)
        assert "connection_usage_warning" in thresholds

    def test_get_monitoring_intervals_enhanced(self):
        """Test getting enhanced monitoring intervals."""
        config_manager = EnhancedHealthConfigurationManager()

        intervals = config_manager.get_monitoring_intervals_enhanced()
        assert isinstance(intervals, dict)
        assert "health_check" in intervals

    def test_export_config_enhanced(self):
        """Test exporting enhanced configuration."""
        config_manager = EnhancedHealthConfigurationManager()

        export = config_manager.export_config_enhanced()
        assert isinstance(export, dict)
        assert "config" in export
        assert "exported_at" in export
        assert "checker_specific_configs" in export

    def test_get_config_summary_enhanced(self):
        """Test getting enhanced configuration summary."""
        config_manager = EnhancedHealthConfigurationManager()

        summary = config_manager.get_config_summary_enhanced()
        assert isinstance(summary, dict)
        assert "base_config" in summary

    def test_optimize_config_for_performance(self):
        """Test optimizing configuration for performance."""
        config_manager = EnhancedHealthConfigurationManager()
        factory = HealthCheckerFactory()
        config_manager.set_health_checker_factory(factory)

        recommendations = config_manager.optimize_config_for_performance()
        assert isinstance(recommendations, dict)
        assert "interval_optimizations" in recommendations

    def test_load_from_environment(self):
        """Test loading configuration from environment variables."""
        config_manager = EnhancedHealthConfigurationManager()

        # Set environment variables
        env_vars = {
            "HEALTH_CHECK_INTERVAL_SECONDS": "60",
            "HEALTH_CHECK_TIMEOUT_SECONDS": "45",
            "HEALTH_DB_THRESHOLD_PERCENT": "90",
        }

        with patch.dict(os.environ, env_vars):
            config_manager.load_from_environment()

            # Check that config was updated
            config = config_manager.get_config()
            assert config.check_interval_seconds == 60
            assert config.timeout_seconds == 45
            assert config.database_connection_threshold_percent == 90

    def test_load_from_environment_invalid_values(self):
        """Test loading configuration with invalid environment values."""
        config_manager = EnhancedHealthConfigurationManager()

        # Set invalid environment variables
        env_vars = {
            "HEALTH_CHECK_INTERVAL_SECONDS": "invalid",
            "HEALTH_CHECK_TIMEOUT_SECONDS": "not_a_number",
        }

        with patch.dict(os.environ, env_vars):
            # Should not raise exception, but should log warnings
            config_manager.load_from_environment()

            # Config should remain unchanged
            config = config_manager.get_config()
            assert config.check_interval_seconds != "invalid"

    def test_validate_config(self):
        """Test configuration validation."""
        config_manager = EnhancedHealthConfigurationManager()

        # Valid config should have no errors
        errors = config_manager.validate_config()
        assert isinstance(errors, list)

    def test_validate_config_invalid(self):
        """Test configuration validation with invalid config."""
        config = HealthCheckConfig(
            check_interval_seconds=-1,
            timeout_seconds=60,
            database_connection_threshold_percent=150  # Invalid: > 100
        )
        config_manager = EnhancedHealthConfigurationManager(config)

        errors = config_manager.validate_config()
        assert len(errors) > 0
        assert any("check_interval_seconds" in error for error in errors)
        assert any("database_connection_threshold_percent" in error for error in errors)

    def test_get_config_history(self):
        """Test getting configuration history."""
        config_manager = EnhancedHealthConfigurationManager()

        # Update config to create history
        config_manager.update_config(timeout_seconds=45)

        history = config_manager.get_config_history()
        assert isinstance(history, list)
        assert len(history) > 0

    def test_get_config_history_with_limit(self):
        """Test getting configuration history with limit."""
        config_manager = EnhancedHealthConfigurationManager()

        # Update config multiple times
        for i in range(5):
            config_manager.update_config(timeout_seconds=30 + i)

        history = config_manager.get_config_history(limit=3)
        assert isinstance(history, list)
        assert len(history) == 3

    def test_export_config(self):
        """Test exporting configuration."""
        config_manager = EnhancedHealthConfigurationManager()

        export = config_manager.export_config()
        assert isinstance(export, dict)
        assert "config" in export
        assert "exported_at" in export
        assert "is_valid" in export

    def test_import_config(self):
        """Test importing configuration."""
        config_manager = EnhancedHealthConfigurationManager()

        config_data = {
            "config": {
                "timeout_seconds": 45,
                "check_interval_seconds": 60,
            }
        }

        success = config_manager.import_config(config_data)
        assert success is True

        # Check that config was updated
        config = config_manager.get_config()
        assert config.timeout_seconds == 45
        assert config.check_interval_seconds == 60

    def test_import_config_invalid(self):
        """Test importing invalid configuration."""
        config_manager = EnhancedHealthConfigurationManager()

        # Invalid config data
        config_data = {"invalid": "data"}

        success = config_manager.import_config(config_data)
        assert success is False

    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        config_manager = EnhancedHealthConfigurationManager()

        # Modify config first
        config_manager.update_config(timeout_seconds=45)
        assert config_manager.get_config().timeout_seconds == 45

        # Reset to defaults
        config_manager.reset_to_defaults()
        assert config_manager.get_config().timeout_seconds == 30  # Default value

    def test_get_component_config(self):
        """Test getting component-specific configuration."""
        config_manager = EnhancedHealthConfigurationManager()

        db_config = config_manager.get_component_config("database")
        assert isinstance(db_config, dict)
        assert "connection_threshold_percent" in db_config

    def test_get_component_config_unknown(self):
        """Test getting configuration for unknown component."""
        config_manager = EnhancedHealthConfigurationManager()

        config = config_manager.get_component_config("unknown_component")
        assert isinstance(config, dict)
        assert "timeout_seconds" in config  # Should have default values

    def test_is_component_enabled(self):
        """Test checking if component is enabled."""
        config_manager = EnhancedHealthConfigurationManager()

        # Test enabled components
        assert config_manager.is_component_enabled("database") is True
        assert config_manager.is_component_enabled("redis") is True

        # Test disabled component
        assert config_manager.is_component_enabled("disabled_component") is False

    def test_get_retry_configuration(self):
        """Test getting retry configuration."""
        config_manager = EnhancedHealthConfigurationManager()

        retry_config = config_manager.get_retry_configuration("database")
        assert isinstance(retry_config, dict)
        assert "max_retries" in retry_config
        assert "backoff_multiplier" in retry_config

    def test_get_retry_configuration_unknown(self):
        """Test getting retry configuration for unknown component."""
        config_manager = EnhancedHealthConfigurationManager()

        retry_config = config_manager.get_retry_configuration("unknown")
        assert isinstance(retry_config, dict)
        assert retry_config["max_retries"] == 2  # Default value