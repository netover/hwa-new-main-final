"""
Test suite for database connection threshold alerting functionality.

Tests the implementation of configurable threshold-based alerting
when active database connections exceed a percentage of total pool capacity.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.connection_pool_manager import ConnectionPoolStats
from resync.core.health_models import HealthCheckConfig, HealthStatus
from resync.core.health_service import HealthCheckService


class TestDatabaseConnectionThreshold:
    """Test database connection threshold alerting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.default_config = HealthCheckConfig()
        self.mock_pool_stats = ConnectionPoolStats(
            pool_name="database",
            active_connections=18,
            idle_connections=2,
            total_connections=20,
            connection_errors=0,
            pool_hits=100,
            pool_misses=5,
            connection_creations=25,
            connection_closures=20,
            waiting_connections=0,
            peak_connections=19,
            average_wait_time=0.05,
            last_health_check=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_threshold_90_percent_below_threshold(self):
        """Test health status is HEALTHY when below 90% threshold."""
        config = HealthCheckConfig(database_connection_threshold_percent=90.0)
        service = HealthCheckService(config)

        # Mock pool stats to be 80% usage (below threshold)
        mock_stats = MagicMock()
        mock_stats.active_connections = 16
        mock_stats.total_connections = 20
        mock_stats.idle_connections = 4
        mock_stats.__dict__.update(vars(self.mock_pool_stats))

        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.acquire_connection.return_value.__aenter__.return_value = (
                MagicMock()
            )
            mock_manager.get_pool_stats.return_value = {"database": mock_stats}
            mock_get_manager.return_value = mock_manager

            health = await service._check_database_health()

            assert health.status == HealthStatus.HEALTHY
            assert "healthy" in health.message.lower()
            assert health.metadata["connection_usage_percent"] == 80.0
            assert health.metadata["threshold_percent"] == 90.0

    @pytest.mark.asyncio
    async def test_threshold_90_percent_at_threshold(self):
        """Test health status is DEGRADED when at 90% threshold."""
        config = HealthCheckConfig(database_connection_threshold_percent=90.0)
        service = HealthCheckService(config)

        # Mock pool stats to be exactly 90% usage
        mock_stats = MagicMock()
        mock_stats.active_connections = 18
        mock_stats.total_connections = 20
        mock_stats.idle_connections = 2
        mock_stats.__dict__.update(vars(self.mock_pool_stats))

        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.acquire_connection.return_value.__aenter__.return_value = (
                MagicMock()
            )
            mock_manager.get_pool_stats.return_value = {"database": mock_stats}
            mock_get_manager.return_value = mock_manager

            health = await service._check_database_health()

            assert health.status == HealthStatus.DEGRADED
            assert "near capacity" in health.message.lower()
            assert health.metadata["connection_usage_percent"] == 90.0
            assert health.metadata["threshold_percent"] == 90.0

    @pytest.mark.asyncio
    async def test_threshold_50_percent_above_threshold(self):
        """Test health status is DEGRADED when above custom 50% threshold."""
        config = HealthCheckConfig(database_connection_threshold_percent=50.0)
        service = HealthCheckService(config)

        # Mock pool stats to be 60% usage (above 50% threshold)
        mock_stats = MagicMock()
        mock_stats.active_connections = 12
        mock_stats.total_connections = 20
        mock_stats.idle_connections = 8
        mock_stats.__dict__.update(vars(self.mock_pool_stats))

        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.acquire_connection.return_value.__aenter__.return_value = (
                MagicMock()
            )
            mock_manager.get_pool_stats.return_value = {"database": mock_stats}
            mock_get_manager.return_value = mock_manager

            health = await service._check_database_health()

            assert health.status == HealthStatus.DEGRADED
            assert "near capacity" in health.message.lower()
            assert health.metadata["connection_usage_percent"] == 60.0
            assert health.metadata["threshold_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_threshold_95_percent_very_high_usage(self):
        """Test health status is DEGRADED at 95% usage with high threshold."""
        config = HealthCheckConfig(database_connection_threshold_percent=95.0)
        service = HealthCheckService(config)

        # Mock pool stats to be 95% usage
        mock_stats = MagicMock()
        mock_stats.active_connections = 19
        mock_stats.total_connections = 20
        mock_stats.idle_connections = 1
        mock_stats.__dict__.update(vars(self.mock_pool_stats))

        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.acquire_connection.return_value.__aenter__.return_value = (
                MagicMock()
            )
            mock_manager.get_pool_stats.return_value = {"database": mock_stats}
            mock_get_manager.return_value = mock_manager

            health = await service._check_database_health()

            assert health.status == HealthStatus.DEGRADED
            assert health.metadata["connection_usage_percent"] == 95.0
            assert health.metadata["threshold_percent"] == 95.0

    @pytest.mark.asyncio
    async def test_alert_generation_for_threshold_breach(self):
        """Test that alerts are generated when threshold is breached."""
        config = HealthCheckConfig(
            database_connection_threshold_percent=75.0, alert_enabled=True
        )
        service = HealthCheckService(config)

        # Create components with database at 80% usage (above 75% threshold)
        components = {
            "database": MagicMock(
                status=HealthStatus.DEGRADED,
                metadata={"connection_usage_percent": 80.0, "threshold_percent": 75.0},
            ),
            "redis": MagicMock(status=HealthStatus.HEALTHY, metadata={}),
            "memory": MagicMock(status=HealthStatus.HEALTHY, metadata={}),
        }

        alerts = service._check_alerts(components)

        assert len(alerts) > 0
        assert any(
            "Database connection pool usage at 80.0%" in alert for alert in alerts
        )
        assert any("threshold: 75.0%" in alert for alert in alerts)

    @pytest.mark.asyncio
    async def test_no_alerts_when_below_threshold(self):
        """Test no specific database alerts when below threshold."""
        config = HealthCheckConfig(
            database_connection_threshold_percent=90.0, alert_enabled=True
        )
        service = HealthCheckService(config)

        # Create components with database at 85% usage (below 90% threshold)
        components = {
            "database": MagicMock(
                status=HealthStatus.HEALTHY,
                metadata={"connection_usage_percent": 85.0, "threshold_percent": 90.0},
            ),
            "redis": MagicMock(status=HealthStatus.HEALTHY, metadata={}),
            "memory": MagicMock(status=HealthStatus.HEALTHY, metadata={}),
        }

        alerts = service._check_alerts(components)

        # Should not have specific database threshold alerts
        database_alerts = [
            alert for alert in alerts if "Database connection pool usage" in alert
        ]
        assert len(database_alerts) == 0

    @pytest.mark.asyncio
    async def test_edge_case_zero_total_connections(self):
        """Test handling of zero total connections edge case."""
        config = HealthCheckConfig(database_connection_threshold_percent=90.0)
        service = HealthCheckService(config)

        # Mock pool stats with zero total connections
        mock_stats = MagicMock()
        mock_stats.active_connections = 0
        mock_stats.total_connections = 0
        mock_stats.idle_connections = 0
        mock_stats.__dict__.update(vars(self.mock_pool_stats))

        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.acquire_connection.return_value.__aenter__.return_value = (
                MagicMock()
            )
            mock_manager.get_pool_stats.return_value = {"database": mock_stats}
            mock_get_manager.return_value = mock_manager

            health = await service._check_database_health()

            assert health.status == HealthStatus.UNHEALTHY
            assert "no configured connections" in health.message.lower()
            assert health.metadata["connection_usage_percent"] == 0.0

    @pytest.mark.asyncio
    async def test_connection_pools_health_check_uses_database_threshold(self):
        """Test that connection pools health check uses database threshold."""
        config = HealthCheckConfig(database_connection_threshold_percent=80.0)
        service = HealthCheckService(config)

        mock_pool_stats_dict = {
            "database": MagicMock(
                active_connections=17, total_connections=20, idle_connections=3
            )
        }

        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_pool_stats.return_value = mock_pool_stats_dict
            mock_get_manager.return_value = mock_manager

            health = await service._check_connection_pools_health()

            # Should be DEGRADED since 17/20 = 85% > 80% threshold
            assert health.status == HealthStatus.DEGRADED
            assert "85.0%" in health.message
            assert "threshold: 80.0%" in health.message

    def test_configurable_threshold_values(self):
        """Test that threshold can be configured with different values."""
        # Test various threshold values
        thresholds = [50.0, 75.0, 80.0, 90.0, 95.0, 99.0]

        for threshold in thresholds:
            config = HealthCheckConfig(database_connection_threshold_percent=threshold)
            assert config.database_connection_threshold_percent == threshold
            assert 0 <= threshold <= 100


if __name__ == "__main__":
    pytest.main([__file__])




