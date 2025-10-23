"""
Tests for Refactored Health Service Orchestrator

This module contains unit tests for the RefactoredHealthServiceOrchestrator class.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.health_models import ComponentHealth, ComponentType, HealthCheckConfig, HealthStatus
from resync.core.health.refactored_health_service_orchestrator import RefactoredHealthServiceOrchestrator


class TestRefactoredHealthServiceOrchestrator:
    """Test cases for RefactoredHealthServiceOrchestrator."""

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        orchestrator = RefactoredHealthServiceOrchestrator()
        assert orchestrator.config_manager is not None
        assert orchestrator.checker_factory is not None
        assert orchestrator.last_health_check is None
        assert len(orchestrator._component_results) == 0

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = HealthCheckConfig(timeout_seconds=60)
        orchestrator = RefactoredHealthServiceOrchestrator(config)
        assert orchestrator.config_manager.get_config().timeout_seconds == 60

    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check_success(self):
        """Test successful comprehensive health check."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Mock the checker factory to return mock checkers
        mock_checker = MagicMock()
        mock_health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.OTHER,
            status=HealthStatus.HEALTHY,
            message="Test healthy",
            last_check=datetime.now(),
        )
        mock_checker.check_health_with_timeout = AsyncMock(return_value=mock_health)

        orchestrator.checker_factory.get_enabled_health_checkers = MagicMock(return_value={
            "test_component": mock_checker
        })
        orchestrator.checker_factory.get_component_type_mapping = MagicMock(return_value={
            "test_component": ComponentType.OTHER
        })

        result = await orchestrator.perform_comprehensive_health_check()

        assert result is not None
        assert result.overall_status == HealthStatus.HEALTHY
        assert len(result.components) == 1
        assert "test_component" in result.components
        assert result.components["test_component"].status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check_with_failures(self):
        """Test comprehensive health check with component failures."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Mock one healthy and one unhealthy checker
        healthy_checker = MagicMock()
        healthy_health = ComponentHealth(
            name="healthy_component",
            component_type=ComponentType.OTHER,
            status=HealthStatus.HEALTHY,
            message="Healthy",
            last_check=datetime.now(),
        )
        healthy_checker.check_health_with_timeout = AsyncMock(return_value=healthy_health)

        unhealthy_checker = MagicMock()
        unhealthy_health = ComponentHealth(
            name="unhealthy_component",
            component_type=ComponentType.OTHER,
            status=HealthStatus.UNHEALTHY,
            message="Unhealthy",
            last_check=datetime.now(),
        )
        unhealthy_checker.check_health_with_timeout = AsyncMock(return_value=unhealthy_health)

        orchestrator.checker_factory.get_enabled_health_checkers = MagicMock(return_value={
            "healthy_component": healthy_checker,
            "unhealthy_component": unhealthy_checker,
        })
        orchestrator.checker_factory.get_component_type_mapping = MagicMock(return_value={
            "healthy_component": ComponentType.OTHER,
            "unhealthy_component": ComponentType.OTHER,
        })

        result = await orchestrator.perform_comprehensive_health_check()

        assert result is not None
        assert result.overall_status == HealthStatus.UNHEALTHY  # Worst status wins
        assert len(result.components) == 2
        assert result.components["healthy_component"].status == HealthStatus.HEALTHY
        assert result.components["unhealthy_component"].status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check_with_timeout(self):
        """Test comprehensive health check with timeout."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Mock checker that times out
        slow_checker = MagicMock()
        async def slow_check():
            await asyncio.sleep(2)  # Longer than timeout
            return MagicMock()
        slow_checker.check_health_with_timeout = slow_check

        orchestrator.checker_factory.get_enabled_health_checkers = MagicMock(return_value={
            "slow_component": slow_checker
        })
        orchestrator.checker_factory.get_component_type_mapping = MagicMock(return_value={
            "slow_component": ComponentType.OTHER
        })

        # Set short timeout
        orchestrator.config_manager.get_config = MagicMock(return_value=HealthCheckConfig(timeout_seconds=0.1))

        result = await orchestrator.perform_comprehensive_health_check()

        assert result is not None
        assert len(result.components) == 1

    @pytest.mark.asyncio
    async def test_get_component_health(self):
        """Test getting health of specific component."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Mock component health in cache
        mock_health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.OTHER,
            status=HealthStatus.HEALTHY,
            message="Test",
            last_check=datetime.now(),
        )
        orchestrator._component_results["test_component"] = mock_health

        result = await orchestrator.get_component_health("test_component")
        assert result == mock_health

    @pytest.mark.asyncio
    async def test_get_component_health_not_found(self):
        """Test getting health of non-existent component."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        result = await orchestrator.get_component_health("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_component_health(self):
        """Test getting all component health results."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Add some mock health results
        mock_health1 = ComponentHealth(
            name="component1",
            component_type=ComponentType.OTHER,
            status=HealthStatus.HEALTHY,
            message="Test 1",
            last_check=datetime.now(),
        )
        mock_health2 = ComponentHealth(
            name="component2",
            component_type=ComponentType.OTHER,
            status=HealthStatus.DEGRADED,
            message="Test 2",
            last_check=datetime.now(),
        )
        orchestrator._component_results = {
            "component1": mock_health1,
            "component2": mock_health2,
        }

        results = await orchestrator.get_all_component_health()
        assert len(results) == 2
        assert "component1" in results
        assert "component2" in results

    def test_get_last_check_time(self):
        """Test getting last check time."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Initially None
        assert orchestrator.get_last_check_time() is None

        # Set a time
        test_time = datetime.now()
        orchestrator.last_health_check = test_time
        assert orchestrator.get_last_check_time() == test_time

    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        metrics = orchestrator.get_performance_metrics()
        assert isinstance(metrics, dict)
        assert "total_checks" in metrics
        assert "successful_checks" in metrics
        assert "failed_checks" in metrics
        assert "average_response_time" in metrics

    def test_get_config_summary(self):
        """Test getting configuration summary."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        summary = orchestrator.get_config_summary()
        assert isinstance(summary, dict)
        assert "base_config" in summary

    def test_validate_configuration(self):
        """Test configuration validation."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        validation = orchestrator.validate_configuration()
        assert isinstance(validation, dict)
        assert "config_validation" in validation
        assert "checker_validation" in validation
        assert "is_valid" in validation

    def test_calculate_overall_status_healthy(self):
        """Test calculating overall status with all healthy components."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        components = {
            "comp1": MagicMock(status=HealthStatus.HEALTHY),
            "comp2": MagicMock(status=HealthStatus.HEALTHY),
        }

        status = orchestrator._calculate_overall_status(components)
        assert status == HealthStatus.HEALTHY

    def test_calculate_overall_status_mixed(self):
        """Test calculating overall status with mixed component statuses."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        components = {
            "comp1": MagicMock(status=HealthStatus.HEALTHY),
            "comp2": MagicMock(status=HealthStatus.DEGRADED),
            "comp3": MagicMock(status=HealthStatus.UNHEALTHY),
        }

        status = orchestrator._calculate_overall_status(components)
        assert status == HealthStatus.UNHEALTHY  # Worst status wins

    def test_generate_summary(self):
        """Test generating health status summary."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        components = {
            "comp1": MagicMock(status=HealthStatus.HEALTHY),
            "comp2": MagicMock(status=HealthStatus.DEGRADED),
            "comp3": MagicMock(status=HealthStatus.UNHEALTHY),
            "comp4": MagicMock(status=HealthStatus.UNKNOWN),
        }

        summary = orchestrator._generate_summary(components)
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1
        assert summary["unhealthy"] == 1
        assert summary["unknown"] == 1

    def test_check_alerts_no_alerts(self):
        """Test checking alerts with no unhealthy components."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        components = {
            "comp1": MagicMock(status=HealthStatus.HEALTHY),
            "comp2": MagicMock(status=HealthStatus.DEGRADED),
        }

        alerts = orchestrator._check_alerts(components)
        assert len(alerts) == 0  # No unhealthy components

    def test_check_alerts_with_alerts(self):
        """Test checking alerts with unhealthy components."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        components = {
            "comp1": MagicMock(status=HealthStatus.UNHEALTHY, metadata={}),
            "comp2": MagicMock(status=HealthStatus.DEGRADED, metadata={}),
        }

        alerts = orchestrator._check_alerts(components)
        assert len(alerts) == 1  # One unhealthy component
        assert "comp1 is unhealthy" in alerts[0]

    def test_update_performance_metrics(self):
        """Test updating performance metrics."""
        orchestrator = RefactoredHealthServiceOrchestrator()

        # Mock a health check result
        result = MagicMock()
        result.summary = {"unhealthy": 0, "unknown": 0}
        result.performance_metrics = {"total_check_time_ms": 100}

        orchestrator._update_performance_metrics(result)

        metrics = orchestrator.get_performance_metrics()
        assert metrics["total_checks"] == 1
        assert metrics["successful_checks"] == 1
        assert metrics["failed_checks"] == 0
        assert metrics["average_response_time"] == 100