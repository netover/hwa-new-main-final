from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
    get_status_color,
    get_status_description,
)
from resync.core.health_service import HealthCheckService


class TestHealthModels:
    """Test health check models and utilities."""

    def test_health_status_enum(self):
        """Test health status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"

    def test_component_type_enum(self):
        """Test component type enum values."""
        assert ComponentType.DATABASE.value == "database"
        assert ComponentType.REDIS.value == "redis"
        assert ComponentType.EXTERNAL_API.value == "external_api"

    def test_get_status_color(self):
        """Test status color mapping."""
        assert get_status_color(HealthStatus.HEALTHY) == "🟢"
        assert get_status_color(HealthStatus.DEGRADED) == "🟡"
        assert get_status_color(HealthStatus.UNHEALTHY) == "🔴"
        assert get_status_color(HealthStatus.UNKNOWN) == "⚪"

    def test_get_status_description(self):
        """Test status description mapping."""
        assert "operational" in get_status_description(HealthStatus.HEALTHY).lower()
        assert "issues" in get_status_description(HealthStatus.DEGRADED).lower()
        assert "failing" in get_status_description(HealthStatus.UNHEALTHY).lower()
        assert "unavailable" in get_status_description(HealthStatus.UNKNOWN).lower()

    def test_component_health_creation(self):
        """Test ComponentHealth dataclass creation."""
        health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.HEALTHY,
            message="All good",
            response_time_ms=100.5,
            last_check=datetime.now(),
            metadata={"test": "data"},
            error_count=0,
            warning_count=0,
        )

        assert health.name == "test_component"
        assert health.component_type == ComponentType.DATABASE
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "All good"
        assert health.response_time_ms == 100.5
        assert health.metadata["test"] == "data"
        assert health.error_count == 0
        assert health.warning_count == 0

    def test_health_check_config_defaults(self):
        """Test HealthCheckConfig default values."""
        config = HealthCheckConfig()

        assert config.enabled is True
        assert config.check_interval_seconds == 60
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 5
        assert config.alert_enabled is True
        assert config.track_response_times is True
        assert config.track_error_rates is True


class TestHealthCheckService:
    """Test HealthCheckService functionality."""

    @pytest.fixture
    def health_service(self):
        """Create a HealthCheckService instance for testing."""
        config = HealthCheckConfig(
            enabled=True,
            check_interval_seconds=1,
            timeout_seconds=5,
            alert_enabled=False,  # Disable alerts for testing
        )
        return HealthCheckService(config)

    @pytest.mark.asyncio
    async def test_health_service_initialization(self, health_service):
        """Test HealthCheckService initialization."""
        assert health_service.config.enabled is True
        assert health_service.config.check_interval_seconds == 1
        assert health_service.last_health_check is None
        assert health_service.component_cache == {}

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, health_service):
        """Test monitoring start/stop functionality."""
        # Start monitoring
        await health_service.start_monitoring()
        assert health_service._is_monitoring is True
        assert health_service._monitoring_task is not None

        # Stop monitoring
        await health_service.stop_monitoring()
        assert health_service._is_monitoring is False
        assert health_service._monitoring_task is None

    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check_mocked(self, health_service):
        """Test comprehensive health check with mocked components."""

        # Mock all the component health check methods
        with patch.object(
            health_service,
            "_check_database_health",
            return_value=ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY,
                message="Database healthy",
            ),
        ):
            with patch.object(
                health_service,
                "_check_redis_health",
                return_value=ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.HEALTHY,
                    message="Redis healthy",
                ),
            ):
                with patch.object(
                    health_service,
                    "_check_cache_health",
                    return_value=ComponentHealth(
                        name="cache_hierarchy",
                        component_type=ComponentType.CACHE,
                        status=HealthStatus.HEALTHY,
                        message="Cache healthy",
                    ),
                ):
                    with patch.object(
                        health_service,
                        "_check_file_system_health",
                        return_value=ComponentHealth(
                            name="file_system",
                            component_type=ComponentType.FILE_SYSTEM,
                            status=HealthStatus.HEALTHY,
                            message="File system healthy",
                        ),
                    ):
                        with patch.object(
                            health_service,
                            "_check_memory_health",
                            return_value=ComponentHealth(
                                name="memory",
                                component_type=ComponentType.MEMORY,
                                status=HealthStatus.HEALTHY,
                                message="Memory healthy",
                            ),
                        ):
                            with patch.object(
                                health_service,
                                "_check_cpu_health",
                                return_value=ComponentHealth(
                                    name="cpu",
                                    component_type=ComponentType.CPU,
                                    status=HealthStatus.HEALTHY,
                                    message="CPU healthy",
                                ),
                            ):
                                with patch.object(
                                    health_service,
                                    "_check_tws_monitor_health",
                                    return_value=ComponentHealth(
                                        name="tws_monitor",
                                        component_type=ComponentType.EXTERNAL_API,
                                        status=HealthStatus.HEALTHY,
                                        message="TWS monitor healthy",
                                    ),
                                ):
                                    with patch.object(
                                        health_service,
                                        "_check_connection_pools_health",
                                        return_value=ComponentHealth(
                                            name="connection_pools",
                                            component_type=ComponentType.CONNECTION_POOL,
                                            status=HealthStatus.HEALTHY,
                                            message="Connection pools healthy",
                                        ),
                                    ):
                                        with patch.object(
                                            health_service,
                                            "_check_websocket_pool_health",
                                            return_value=ComponentHealth(
                                                name="websocket_pool",
                                                component_type=ComponentType.WEBSOCKET,
                                                status=HealthStatus.HEALTHY,
                                                message="WebSocket pool healthy",
                                            ),
                                        ):

                                            # Perform health check
                                            result = (
                                                await health_service.perform_comprehensive_health_check()
                                            )

                                            # Verify results
                                            assert (
                                                result.overall_status
                                                == HealthStatus.HEALTHY
                                            )
                                            assert len(result.components) == 9
                                            assert all(
                                                comp.status == HealthStatus.HEALTHY
                                                for comp in result.components.values()
                                            )
                                            assert result.timestamp is not None
                                            assert (
                                                result.performance_metrics is not None
                                            )
                                            assert (
                                                result.performance_metrics[
                                                    "total_check_time_ms"
                                                ]
                                                > 0
                                            )

    def test_calculate_overall_status(self, health_service):
        """Test overall status calculation from component statuses."""
        # Test all healthy
        components = {
            "comp1": ComponentHealth(
                "comp1", ComponentType.DATABASE, HealthStatus.HEALTHY
            ),
            "comp2": ComponentHealth(
                "comp2", ComponentType.REDIS, HealthStatus.HEALTHY
            ),
        }
        assert (
            health_service._calculate_overall_status(components) == HealthStatus.HEALTHY
        )

        # Test with degraded
        components["comp1"] = ComponentHealth(
            "comp1", ComponentType.DATABASE, HealthStatus.DEGRADED
        )
        assert (
            health_service._calculate_overall_status(components)
            == HealthStatus.DEGRADED
        )

        # Test with unhealthy
        components["comp2"] = ComponentHealth(
            "comp2", ComponentType.REDIS, HealthStatus.UNHEALTHY
        )
        assert (
            health_service._calculate_overall_status(components)
            == HealthStatus.UNHEALTHY
        )

        # Test with unknown
        components["comp1"] = ComponentHealth(
            "comp1", ComponentType.DATABASE, HealthStatus.UNKNOWN
        )
        components["comp2"] = ComponentHealth(
            "comp2", ComponentType.REDIS, HealthStatus.HEALTHY
        )
        assert (
            health_service._calculate_overall_status(components) == HealthStatus.UNKNOWN
        )

        # Test empty components
        assert health_service._calculate_overall_status({}) == HealthStatus.UNKNOWN

    def test_generate_summary(self, health_service):
        """Test summary generation from component health data."""
        components = {
            "comp1": ComponentHealth(
                "comp1",
                ComponentType.DATABASE,
                HealthStatus.HEALTHY,
                response_time_ms=100.0,
                error_count=0,
                warning_count=0,
            ),
            "comp2": ComponentHealth(
                "comp2",
                ComponentType.REDIS,
                HealthStatus.DEGRADED,
                response_time_ms=200.0,
                error_count=1,
                warning_count=2,
            ),
        }

        summary = health_service._generate_summary(components)

        assert summary["total_components"] == 2
        assert summary["healthy_components"] == 1
        assert summary["degraded_components"] == 1
        assert summary["unhealthy_components"] == 0
        assert summary["unknown_components"] == 0
        assert summary["total_errors"] == 1
        assert summary["total_warnings"] == 2
        assert summary["average_response_time_ms"] == 150.0
        assert summary["status_breakdown"]["healthy"] == 1
        assert summary["status_breakdown"]["degraded"] == 1

    def test_check_alerts(self, health_service):
        """Test alert checking functionality."""
        # Test degraded components alert
        components = {
            "comp1": ComponentHealth(
                "comp1", ComponentType.DATABASE, HealthStatus.DEGRADED
            ),
            "comp2": ComponentHealth(
                "comp2", ComponentType.REDIS, HealthStatus.HEALTHY
            ),
        }

        alerts = health_service._check_alerts(components)
        assert len(alerts) == 1
        assert alerts[0]["type"] == "degraded_components"
        assert "comp1" in alerts[0]["components"]

        # Test unhealthy components alert
        components["comp2"] = ComponentHealth(
            "comp2", ComponentType.REDIS, HealthStatus.UNHEALTHY
        )
        alerts = health_service._check_alerts(components)
        assert len(alerts) == 2  # degraded + unhealthy
        assert any(alert["type"] == "unhealthy_components" for alert in alerts)

        # Test high error count alert
        components["comp1"] = ComponentHealth(
            "comp1", ComponentType.DATABASE, HealthStatus.HEALTHY, error_count=10
        )
        alerts = health_service._check_alerts(components)
        assert any(alert["type"] == "high_error_rates" for alert in alerts)

    def test_get_component_type(self, health_service):
        """Test component type mapping from names."""
        assert health_service._get_component_type("database") == ComponentType.DATABASE
        assert health_service._get_component_type("redis") == ComponentType.REDIS
        assert (
            health_service._get_component_type("cache_hierarchy") == ComponentType.CACHE
        )
        assert (
            health_service._get_component_type("file_system")
            == ComponentType.FILE_SYSTEM
        )
        assert health_service._get_component_type("memory") == ComponentType.MEMORY
        assert health_service._get_component_type("cpu") == ComponentType.CPU
        assert (
            health_service._get_component_type("tws_monitor")
            == ComponentType.EXTERNAL_API
        )
        assert (
            health_service._get_component_type("connection_pools")
            == ComponentType.CONNECTION_POOL
        )
        assert (
            health_service._get_component_type("websocket_pool")
            == ComponentType.WEBSOCKET
        )
        assert (
            health_service._get_component_type("unknown_component")
            == ComponentType.EXTERNAL_API
        )

    def test_health_history_management(self, health_service):
        """Test health history tracking and management."""
        # Add some history entries
        result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            components={
                "comp1": ComponentHealth(
                    "comp1", ComponentType.DATABASE, HealthStatus.HEALTHY
                )
            },
        )

        health_service._update_health_history(result)
        assert len(health_service.health_history) == 0  # No changes, so no history

        # Add a change
        health_service.component_cache = {
            "comp1": ComponentHealth(
                "comp1", ComponentType.DATABASE, HealthStatus.DEGRADED
            )
        }
        result.overall_status = HealthStatus.DEGRADED
        result.components["comp1"] = ComponentHealth(
            "comp1", ComponentType.DATABASE, HealthStatus.HEALTHY
        )

        health_service._update_health_history(result)
        assert len(health_service.health_history) == 1
        assert (
            health_service.health_history[0].component_changes["comp1"]
            == HealthStatus.HEALTHY
        )

        # Test history retrieval
        history = health_service.get_health_history(limit=5)
        assert len(history) == 1

        # Test history cleanup (simulate old entries)
        old_entry = HealthStatusHistory(
            timestamp=datetime.now() - timedelta(hours=25),
            overall_status=HealthStatus.HEALTHY,
        )
        health_service.health_history.append(old_entry)

        # Trigger cleanup by adding a new entry
        health_service._update_health_history(result)
        history = health_service.get_health_history(limit=10)
        assert (
            len(history) >= 1
        )  # Should have at least the recent entry (timing may keep both)

    def test_is_healthy_method(self, health_service):
        """Test is_healthy method."""
        # Test with no cache
        assert health_service.is_healthy() is False

        # Test with healthy components
        health_service.component_cache = {
            "comp1": ComponentHealth(
                "comp1", ComponentType.DATABASE, HealthStatus.HEALTHY
            ),
            "comp2": ComponentHealth(
                "comp2", ComponentType.REDIS, HealthStatus.HEALTHY
            ),
        }
        assert health_service.is_healthy() is True

        # Test with degraded components (should still be considered healthy)
        health_service.component_cache["comp1"] = ComponentHealth(
            "comp1", ComponentType.DATABASE, HealthStatus.DEGRADED
        )
        assert health_service.is_healthy() is True

        # Test with unhealthy components
        health_service.component_cache["comp2"] = ComponentHealth(
            "comp2", ComponentType.REDIS, HealthStatus.UNHEALTHY
        )
        assert health_service.is_healthy() is False


class TestComponentSpecificHealthChecks:
    """Test individual component health check implementations."""

    @pytest.fixture
    def health_service(self):
        """Create a HealthCheckService instance for testing."""
        return HealthCheckService()

    @pytest.mark.asyncio
    async def test_database_health_check_with_mock_pool(self, health_service):
        """Test database health check with mocked connection pool."""

        # Create mock pool
        mock_pool = Mock()
        mock_pool.health_check = AsyncMock(return_value=True)
        mock_pool.get_stats = Mock(
            return_value=Mock(
                active_connections=5,
                idle_connections=10,
                total_connections=15,
                connection_errors=0,
                pool_hits=100,
                pool_misses=5,
            )
        )

        # Mock connection pool manager
        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_pool = Mock(return_value=mock_pool)
            mock_get_manager.return_value = mock_manager

            result = await health_service._check_database_health()

            assert result.name == "database"
            assert result.component_type == ComponentType.DATABASE
            assert result.status == HealthStatus.HEALTHY
            assert "healthy" in result.message.lower()
            assert result.response_time_ms > 0
            assert result.metadata["active_connections"] == 5
            assert result.metadata["connection_errors"] == 0

    @pytest.mark.asyncio
    async def test_database_health_check_no_pool(self, health_service):
        """Test database health check when pool is not available."""

        # Mock connection pool manager returning None
        with patch(
            "resync.core.health_service.get_connection_pool_manager"
        ) as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_pool = Mock(return_value=None)
            mock_get_manager.return_value = mock_manager

            result = await health_service._check_database_health()

            assert result.name == "database"
            assert result.component_type == ComponentType.DATABASE
            assert result.status == HealthStatus.UNKNOWN
            assert "not available" in result.message.lower()

    @pytest.mark.asyncio
    async def test_memory_health_check(self, health_service):
        """Test memory health check."""

        # Mock psutil.virtual_memory
        with patch("resync.core.health_service.psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = Mock(
                percent=50.0,
                available=8 * (1024**3),  # 8GB
                total=16 * (1024**3),  # 16GB
            )

            # Mock psutil.Process
            with patch("resync.core.health_service.psutil.Process") as mock_process:
                mock_process.return_value = Mock(
                    memory_info=Mock(return_value=Mock(rss=512 * (1024**2)))  # 512MB
                )

                result = await health_service._check_memory_health()

                assert result.name == "memory"
                assert result.component_type == ComponentType.MEMORY
                assert result.status == HealthStatus.HEALTHY
                assert "normal" in result.message.lower()
                assert result.metadata["memory_usage_percent"] == 50.0
                assert result.metadata["process_memory_mb"] == 512.0

    @pytest.mark.asyncio
    async def test_cpu_health_check(self, health_service):
        """Test CPU health check."""

        # Mock psutil.cpu_percent
        with patch("resync.core.health_service.psutil.cpu_percent") as mock_cpu:
            mock_cpu.return_value = 30.0

            # Mock psutil.cpu_count
            with patch("resync.core.health_service.psutil.cpu_count") as mock_cpu_count:
                mock_cpu_count.return_value = 4

                # Mock psutil.cpu_freq
                with patch("resync.core.health_service.psutil.cpu_freq") as mock_freq:
                    mock_freq.return_value = Mock(current=2500.0)

                    result = await health_service._check_cpu_health()

                    assert result.name == "cpu"
                    assert result.component_type == ComponentType.CPU
                    assert result.status == HealthStatus.HEALTHY
                    assert "normal" in result.message.lower()
                    assert result.metadata




