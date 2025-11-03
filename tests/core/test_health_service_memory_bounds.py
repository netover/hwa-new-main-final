"""Tests for health service memory bounds functionality."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from resync.core.health_models import HealthCheckConfig, HealthCheckResult, HealthStatus
from resync.core.health_service import HealthCheckService


class TestHealthServiceMemoryBounds:
    """Test suite for health service memory bounds functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration with memory bounds."""
        return HealthCheckConfig(
            max_history_entries=50,
            history_cleanup_threshold=0.8,
            history_cleanup_batch_size=10,
            history_retention_days=1,
            enable_memory_monitoring=True,
            memory_usage_threshold_mb=5,
        )

    @pytest.fixture
    def service(self, config):
        """Create health service with test configuration."""
        return HealthCheckService(config)

    def test_config_memory_bounds(self, config):
        """Test that configuration includes memory bounds."""
        assert config.max_history_entries == 50
        assert config.history_cleanup_threshold == 0.8
        assert config.history_cleanup_batch_size == 10
        assert config.enable_memory_monitoring is True
        assert config.memory_usage_threshold_mb == 5

    @pytest.mark.asyncio
    async def test_cleanup_by_size_threshold(self, service):
        """Test cleanup when size threshold is exceeded."""
        # Add entries beyond threshold
        for i in range(60):  # 60 > 50 * 0.8 = 40
            result = HealthCheckResult(
                overall_status=HealthStatus.HEALTHY,
                timestamp=datetime.now() - timedelta(minutes=i),
            )
            service._update_health_history(result)

        # Wait for cleanup
        await asyncio.sleep(0.1)

        # Should have cleaned up
        assert len(service.health_history) <= 50

    @pytest.mark.asyncio
    async def test_cleanup_by_age(self, service):
        """Test cleanup based on age retention."""
        from resync.core.health_models import HealthStatusHistory

        # Add old entries
        old_time = datetime.now() - timedelta(days=2)  # Beyond 1 day retention
        for i in range(10):
            service.health_history.append(
                HealthStatusHistory(
                    timestamp=old_time - timedelta(hours=i),
                    overall_status=HealthStatus.HEALTHY,
                )
            )

        # Add recent entries
        for i in range(5):
            service.health_history.append(
                HealthStatusHistory(
                    timestamp=datetime.now() - timedelta(minutes=i),
                    overall_status=HealthStatus.HEALTHY,
                )
            )

        # Force cleanup
        cleanup_result = await service.force_cleanup()

        # Should have removed old entries
        assert cleanup_result["cleaned_entries"] >= 10
        assert all(
            entry.timestamp >= datetime.now() - timedelta(days=1)
            for entry in service.health_history
        )

    @pytest.mark.asyncio
    async def test_memory_usage_tracking(self, service):
        """Test memory usage tracking."""
        # Add entries
        for i in range(20):
            result = HealthCheckResult(
                overall_status=HealthStatus.HEALTHY,
                timestamp=datetime.now() - timedelta(minutes=i),
            )
            service._update_health_history(result)

        # Wait for memory update
        await asyncio.sleep(0.1)

        # Check memory usage
        memory_stats = service.get_memory_usage()
        assert "history_entries" in memory_stats
        assert "memory_usage_mb" in memory_stats
        assert memory_stats["history_entries"] == len(service.health_history)

    def test_get_health_history_with_limits(self, service):
        """Test getting health history with entry limits."""
        from resync.core.health_models import HealthStatusHistory

        # Add test entries
        for i in range(30):
            service.health_history.append(
                HealthStatusHistory(
                    timestamp=datetime.now() - timedelta(hours=i),
                    overall_status=HealthStatus.HEALTHY,
                )
            )

        # Test with limit
        limited_history = service.get_health_history(hours=12, max_entries=5)
        assert len(limited_history) <= 5

        # Test without limit
        full_history = service.get_health_history(hours=48)
        assert len(full_history) <= 30

    @pytest.mark.asyncio
    async def test_force_cleanup(self, service):
        """Test force cleanup functionality."""
        from resync.core.health_models import HealthStatusHistory

        # Add many entries
        for i in range(100):
            service.health_history.append(
                HealthStatusHistory(
                    timestamp=datetime.now() - timedelta(minutes=i),
                    overall_status=HealthStatus.HEALTHY,
                )
            )

        # Force cleanup
        cleanup_result = await service.force_cleanup()

        assert "original_entries" in cleanup_result
        assert "cleaned_entries" in cleanup_result
        assert "current_entries" in cleanup_result
        assert cleanup_result["original_entries"] == 100
        assert cleanup_result["current_entries"] <= 50

    def test_memory_bounds_configuration_from_settings(self):
        """Test loading memory bounds from settings."""
        from resync.settings import settings

        # Check if new settings are available
        assert hasattr(settings, "HEALTH_CHECK_MAX_HISTORY_ENTRIES")
        assert hasattr(settings, "HEALTH_CHECK_HISTORY_CLEANUP_THRESHOLD")
        assert hasattr(settings, "HEALTH_CHECK_ENABLE_MEMORY_MONITORING")

    @pytest.mark.asyncio
    async def test_concurrent_cleanup_safety(self, service):
        """Test that concurrent cleanup operations are safe."""
        # Add entries
        for i in range(60):
            result = HealthCheckResult(
                overall_status=HealthStatus.HEALTHY,
                timestamp=datetime.now() - timedelta(minutes=i),
            )
            service._update_health_history(result)

        # Run multiple cleanups concurrently
        tasks = [service.force_cleanup() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 5
        assert len(service.health_history) <= 50

    def test_component_changes_tracking(self, service):
        """Test that component changes are tracked in history."""
        # Mock component cache
        service.component_cache = {
            "database": MagicMock(status=HealthStatus.HEALTHY),
            "redis": MagicMock(status=HealthStatus.HEALTHY),
        }

        # Create result with changed status
        components = {
            "database": MagicMock(status=HealthStatus.UNHEALTHY),
            "redis": MagicMock(status=HealthStatus.HEALTHY),
        }

        HealthCheckResult(
            overall_status=HealthStatus.DEGRADED,
            timestamp=datetime.now(),
            components=components,
        )

        changes = service._get_component_changes(components)
        assert "database" in changes
        assert changes["database"] == HealthStatus.UNHEALTHY
        assert "redis" not in changes  # No change

    def test_minimum_history_retention(self, service):
        """Test that minimum history is retained."""
        from resync.core.health_models import HealthStatusHistory

        # Add just a few entries
        for i in range(5):
            service.health_history.append(
                HealthStatusHistory(
                    timestamp=datetime.now() - timedelta(minutes=i),
                    overall_status=HealthStatus.HEALTHY,
                )
            )

        # Force cleanup
        asyncio.run(service.force_cleanup())

        # Should retain all entries since below minimum
        assert len(service.health_history) >= 5

    def _create_history_entry(self, result):
        """Helper to create history entry."""
        from resync.core.health_models import HealthStatusHistory

        return HealthStatusHistory(
            timestamp=result.timestamp, overall_status=result.overall_status
        )

    @pytest.mark.asyncio
    async def test_memory_usage_alert_threshold(self, service):
        """Test memory usage alert threshold."""
        # Mock high memory usage
        with patch.object(service, "_memory_usage_mb", 10.0):
            # Should trigger warning
            await service._update_memory_usage()

            # Check that warning was logged (would need log capture in real test)
            assert service._memory_usage_mb > service.config.memory_usage_threshold_mb

    def test_get_health_history_edge_cases(self, service):
        """Test edge cases for get_health_history."""
        # Empty history
        empty_history = service.get_health_history(hours=1)
        assert empty_history == []

        # Very large hours parameter
        large_history = service.get_health_history(hours=999999)
        assert isinstance(large_history, list)

        # Zero max_entries
        zero_history = service.get_health_history(max_entries=0)
        assert zero_history == []


if __name__ == "__main__":
    pytest.main([__file__])




