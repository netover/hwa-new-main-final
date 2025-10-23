"""
Tests for Database Health Checker

This module contains unit tests for the DatabaseHealthChecker class.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.health_models import ComponentType, HealthCheckConfig, HealthStatus
from resync.core.health.health_checkers.database_health_checker import DatabaseHealthChecker


class TestDatabaseHealthChecker:
    """Test cases for DatabaseHealthChecker."""

    def test_initialization(self):
        """Test initialization of database health checker."""
        checker = DatabaseHealthChecker()
        assert checker.component_name == "database"
        assert checker.component_type == ComponentType.DATABASE
        assert checker.config is not None

    @pytest.mark.asyncio
    async def test_check_health_successful(self):
        """Test successful database health check."""
        checker = DatabaseHealthChecker()

        # Mock connection pool manager
        mock_pool_manager = MagicMock()
        mock_connection = MagicMock()

        # Mock database connection behavior
        mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_connection.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone = AsyncMock()
        mock_connection.execute.return_value = mock_result

        mock_pool_manager.acquire_connection = MagicMock(return_value=mock_connection)

        # Mock pool stats
        mock_pool_stats = MagicMock()
        mock_pool_stats.active_connections = 5
        mock_pool_stats.idle_connections = 10
        mock_pool_stats.total_connections = 15
        mock_pool_stats.connection_errors = 0
        mock_pool_stats.pool_hits = 100
        mock_pool_stats.pool_misses = 5
        mock_pool_stats.connection_creations = 20
        mock_pool_stats.connection_closures = 5
        mock_pool_stats.waiting_connections = 0
        mock_pool_stats.peak_connections = 18
        mock_pool_stats.average_wait_time = 0.1
        mock_pool_stats.last_health_check = datetime.now()

        mock_pool_manager.get_pool_stats = MagicMock(return_value={
            "database": mock_pool_stats
        })

        with patch('resync.core.health.health_checkers.database_health_checker.get_connection_pool_manager',
                  return_value=mock_pool_manager):
            result = await checker.check_health()

        assert result.status == HealthStatus.HEALTHY
        assert result.component_type == ComponentType.DATABASE
        assert result.name == "database"
        assert result.response_time_ms is not None
        assert result.last_check is not None
        assert "connection_usage_percent" in result.metadata

    @pytest.mark.asyncio
    async def test_check_health_no_pool_manager(self):
        """Test database health check when pool manager is not available."""
        checker = DatabaseHealthChecker()

        with patch('resync.core.health.health_checkers.database_health_checker.get_connection_pool_manager',
                  return_value=None):
            result = await checker.check_health()

        assert result.status == HealthStatus.UNKNOWN
        assert "Database connection pool not available" in result.message

    @pytest.mark.asyncio
    async def test_check_health_connection_failure(self):
        """Test database health check with connection failure."""
        checker = DatabaseHealthChecker()

        # Mock connection pool manager that raises exception
        mock_pool_manager = MagicMock()
        mock_connection = MagicMock()

        mock_connection.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_pool_manager.acquire_connection = MagicMock(return_value=mock_connection)

        with patch('resync.core.health.health_checkers.database_health_checker.get_connection_pool_manager',
                  return_value=mock_pool_manager):
            result = await checker.check_health()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Database connection failed" in result.message
        assert result.error_count == 1

    @pytest.mark.asyncio
    async def test_check_health_high_connection_usage(self):
        """Test database health check with high connection usage."""
        checker = DatabaseHealthChecker(HealthCheckConfig(database_connection_threshold_percent=50))

        # Mock pool manager with high connection usage
        mock_pool_manager = MagicMock()
        mock_connection = MagicMock()

        mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_connection.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone = AsyncMock()
        mock_connection.execute.return_value = mock_result

        mock_pool_manager.acquire_connection = MagicMock(return_value=mock_connection)

        # Mock pool stats with high usage (80% > 50% threshold)
        mock_pool_stats = MagicMock()
        mock_pool_stats.active_connections = 8
        mock_pool_stats.idle_connections = 2
        mock_pool_stats.total_connections = 10
        mock_pool_stats.connection_errors = 0
        mock_pool_stats.pool_hits = 100
        mock_pool_stats.pool_misses = 5
        mock_pool_stats.connection_creations = 20
        mock_pool_stats.connection_closures = 5
        mock_pool_stats.waiting_connections = 0
        mock_pool_stats.peak_connections = 10
        mock_pool_stats.average_wait_time = 0.1
        mock_pool_stats.last_health_check = datetime.now()

        mock_pool_manager.get_pool_stats = MagicMock(return_value={
            "database": mock_pool_stats
        })

        with patch('resync.core.health.health_checkers.database_health_checker.get_connection_pool_manager',
                  return_value=mock_pool_manager):
            result = await checker.check_health()

        assert result.status == HealthStatus.DEGRADED
        assert "near capacity" in result.message
        assert result.metadata["connection_usage_percent"] == 80.0

    @pytest.mark.asyncio
    async def test_check_health_empty_pool_stats(self):
        """Test database health check with empty pool stats."""
        checker = DatabaseHealthChecker()

        mock_pool_manager = MagicMock()
        mock_connection = MagicMock()

        mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_connection.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone = AsyncMock()
        mock_connection.execute.return_value = mock_result

        mock_pool_manager.acquire_connection = MagicMock(return_value=mock_connection)
        mock_pool_manager.get_pool_stats = MagicMock(return_value={})  # Empty stats

        with patch('resync.core.health.health_checkers.database_health_checker.get_connection_pool_manager',
                  return_value=mock_pool_manager):
            result = await checker.check_health()

        assert result.status == HealthStatus.UNHEALTHY
        assert "unavailable" in result.message

    @pytest.mark.asyncio
    async def test_check_health_missing_database_pool(self):
        """Test database health check when database pool is missing."""
        checker = DatabaseHealthChecker()

        mock_pool_manager = MagicMock()
        mock_connection = MagicMock()

        mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_connection.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone = AsyncMock()
        mock_connection.execute.return_value = mock_result

        mock_pool_manager.acquire_connection = MagicMock(return_value=mock_connection)
        mock_pool_manager.get_pool_stats = MagicMock(return_value={
            "other_pool": MagicMock()  # No database pool
        })

        with patch('resync.core.health.health_checkers.database_health_checker.get_connection_pool_manager',
                  return_value=mock_pool_manager):
            result = await checker.check_health()

        assert result.status == HealthStatus.UNHEALTHY
        assert "missing" in result.message

    def test_get_component_config(self):
        """Test getting database-specific configuration."""
        checker = DatabaseHealthChecker()

        config = checker.get_component_config()
        assert isinstance(config, dict)
        assert "timeout_seconds" in config
        assert "retry_attempts" in config
        assert "connection_threshold_percent" in config

    def test_validate_config(self):
        """Test configuration validation."""
        checker = DatabaseHealthChecker()

        errors = checker.validate_config()
        assert isinstance(errors, list)
        # Should be valid with default config

    def test_validate_config_invalid(self):
        """Test configuration validation with invalid config."""
        config = HealthCheckConfig(timeout_seconds=-1)
        checker = DatabaseHealthChecker(config)

        errors = checker.validate_config()
        assert len(errors) > 0
        assert any("timeout_seconds" in error for error in errors)

    @pytest.mark.asyncio
    async def test_check_health_with_timeout_success(self):
        """Test health check with timeout wrapper - success case."""
        checker = DatabaseHealthChecker()

        # Mock successful health check
        mock_result = MagicMock()
        mock_result.response_time_ms = None
        checker.check_health = AsyncMock(return_value=mock_result)

        result = await checker.check_health_with_timeout(timeout_seconds=30)

        assert result == mock_result
        assert result.response_time_ms is not None
        checker.check_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_with_timeout_exception(self):
        """Test health check with timeout wrapper - exception case."""
        checker = DatabaseHealthChecker()

        # Mock health check that raises exception
        test_exception = Exception("Database error")
        checker.check_health = AsyncMock(side_effect=test_exception)

        result = await checker.check_health_with_timeout(timeout_seconds=30)

        assert result.status == ComponentType.DATABASE  # Exception status mapping
        assert "Database error" in result.message
        assert result.error_count == 1

    def test_get_status_for_exception(self):
        """Test exception status mapping."""
        checker = DatabaseHealthChecker()

        exception = Exception("Test error")
        status = checker._get_status_for_exception(exception)

        assert status == ComponentType.DATABASE