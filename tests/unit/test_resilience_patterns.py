"""
Test suite for resilience patterns implementation.

This module tests the newly implemented resilience patterns for external service calls
to ensure they work correctly and don't break existing functionality.
"""

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from resync.core.resilience import CircuitBreakerError, CircuitBreakerManager
from resync.core.teams_integration import TeamsConfig, TeamsIntegration, TeamsNotification


class TestTeamsIntegrationResilience:
    """Test resilience patterns in Teams Integration."""

    @pytest.fixture
    def teams_config(self):
        """Create a test Teams configuration."""
        return TeamsConfig(
            enabled=True,
            webhook_url="https://outlook.office.com/webhook/test",
            bot_name="Test Bot"
        )

    @pytest.fixture
    def teams_integration(self, teams_config):
        """Create a Teams integration instance with resilience patterns."""
        return TeamsIntegration(teams_config)

    @pytest.mark.asyncio
    async def test_teams_circuit_breaker_initialization(self, teams_integration):
        """Test that circuit breakers are properly initialized."""
        assert hasattr(teams_integration, 'circuit_breaker_manager')
        assert teams_integration.circuit_breaker_manager.state("teams_webhook") == "closed"
        assert teams_integration.circuit_breaker_manager.state("teams_health_check") == "closed"

    @pytest.mark.asyncio
    async def test_teams_backpressure_mechanism(self, teams_integration):
        """Test that backpressure mechanism is properly initialized."""
        assert hasattr(teams_integration, '_notification_semaphore')
        assert teams_integration._notification_semaphore._value == 10  # Default limit

    @pytest.mark.asyncio
    async def test_teams_notification_with_resilience_success(self, teams_integration):
        """Test successful notification with resilience patterns."""
        notification = TeamsNotification(
            title="Test Notification",
            message="This is a test message",
            severity="info"
        )

        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200

        with patch.object(teams_integration, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session

            # Test successful notification
            result = await teams_integration.send_notification(notification)
            assert result is True

    @pytest.mark.asyncio
    async def test_teams_notification_retry_on_failure(self, teams_integration):
        """Test retry mechanism on notification failure."""
        notification = TeamsNotification(
            title="Test Notification",
            message="This is a test message",
            severity="info"
        )

        # Mock failing HTTP response that succeeds on retry
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"

        call_count = 0
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails
                raise aiohttp.ClientError("Connection failed")
            # Second call succeeds
            mock_response.status = 200
            return mock_response

        with patch.object(teams_integration, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.post.side_effect = mock_post
            mock_get_session.return_value = mock_session

            # Test notification with retry
            result = await teams_integration.send_notification(notification)
            assert result is True
            assert call_count == 2  # Should have retried once

    @pytest.mark.asyncio
    async def test_teams_circuit_breaker_opens_on_failures(self, teams_integration):
        """Test that circuit breaker opens after consecutive failures."""
        notification = TeamsNotification(
            title="Test Notification",
            message="This is a test message",
            severity="info"
        )

        # Mock consistently failing HTTP response
        with patch.object(teams_integration, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.post.side_effect = aiohttp.ClientError("Connection failed")
            mock_get_session.return_value = mock_session

            # Send multiple notifications to trigger circuit breaker
            for _ in range(4):  # More than fail_max (3)
                await teams_integration.send_notification(notification)

            # Circuit breaker should be open
            assert teams_integration.circuit_breaker_manager.state("teams_webhook") == "open"

    @pytest.mark.asyncio
    async def test_teams_health_check_with_resilience(self, teams_integration):
        """Test health check with resilience patterns."""
        # Mock successful health check response
        mock_response = AsyncMock()
        mock_response.status = 200

        with patch.object(teams_integration, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session

            # Test health check
            health = await teams_integration.health_check()
            assert health["enabled"] is True
            assert health["configured"] is True
            assert "circuit_breaker_state" in health


class TestResiliencePatternsIntegration:
    """Test integration of resilience patterns across services."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_manager_functionality(self):
        """Test CircuitBreakerManager functionality."""
        cbm = CircuitBreakerManager()
        cbm.register("test_service", fail_max=2, reset_timeout=30)

        # Initially closed
        assert cbm.state("test_service") == "closed"

        # Test calling with circuit breaker
        call_count = 0
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise aiohttp.ClientError("Test error")

        # Should fail and open circuit breaker after fail_max attempts
        for _ in range(3):
            with contextlib.suppress(aiohttp.ClientError, CircuitBreakerError):
                await cbm.call("test_service", failing_function)

        # Circuit should be open after failures
        assert cbm.state("test_service") == "open"

    @pytest.mark.asyncio
    async def test_retry_with_backoff_functionality(self):
        """Test retry_with_backoff functionality."""
        attempt_count = 0

        async def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise aiohttp.ClientError("Temporary failure")
            return "success"

        # Test retry mechanism
        result = await retry_with_backoff_async(
            flaky_function,
            retries=3,
            base_delay=0.1,
            cap=1.0,
            jitter=True,
            retry_on=(aiohttp.ClientError,)
        )

        assert result == "success"
        assert attempt_count == 3  # Should have succeeded on third attempt

    @pytest.mark.asyncio
    async def test_backpressure_mechanisms(self):
        """Test backpressure mechanisms across services."""
        # Test Teams integration backpressure
        teams_config = TeamsConfig(
            enabled=True,
            webhook_url="https://outlook.office.com/webhook/test"
        )
        teams_integration = TeamsIntegration(teams_config)

        # Verify semaphore is initialized
        assert teams_integration._notification_semaphore._value == 10

        # Test SIEM connector backpressure
        siem_config = SIEMConfiguration(
            siem_type=SIEMType.SPLUNK,
            name="test_splunk",
            endpoint_url="https://splunk.example.com:8088",
            api_key="test_api_key"
        )
        splunk_connector = SplunkConnector(siem_config)

        # Verify semaphore is initialized
        assert splunk_connector._send_semaphore._value == 5


class TestBackwardCompatibility:
    """Test that existing functionality is not broken by resilience patterns."""

    @pytest.mark.asyncio
    async def test_teams_integration_interface_unchanged(self):
        """Test that TeamsIntegration public interface remains unchanged."""
        teams_config = TeamsConfig(
            enabled=True,
            webhook_url="https://outlook.office.com/webhook/test"
        )
        teams_integration = TeamsIntegration(teams_config)

        # Test that all expected methods exist
        assert hasattr(teams_integration, 'send_notification')
        assert hasattr(teams_integration, 'health_check')
        assert hasattr(teams_integration, 'monitor_job_status')
        assert hasattr(teams_integration, 'shutdown')

        # Test that method signatures are unchanged
        notification = TeamsNotification(
            title="Test",
            message="Test message",
            severity="info"
        )

        # Should return bool as before
        assert isinstance(await teams_integration.send_notification(notification), bool)

        # Health check should return dict as before
        health = await teams_integration.health_check()
        assert isinstance(health, dict)

    @pytest.mark.asyncio
    async def test_siem_connector_interface_unchanged(self):
        """Test that SIEM connector interfaces remain unchanged."""
        siem_config = SIEMConfiguration(
            siem_type=SIEMType.SPLUNK,
            name="test_splunk",
            endpoint_url="https://splunk.example.com:8088",
            api_key="test_api_key"
        )
        splunk_connector = SplunkConnector(siem_config)

        # Test that all expected methods exist
        assert hasattr(splunk_connector, 'connect')
        assert hasattr(splunk_connector, 'disconnect')
        assert hasattr(splunk_connector, 'send_event')
        assert hasattr(splunk_connector, 'send_events_batch')
        assert hasattr(splunk_connector, 'health_check')

        # Test that method signatures are unchanged
        event = SIEMEvent(
            event_id="test_event",
            timestamp=time.time(),
            source="test_source",
            event_type="test_event",
            severity="medium",
            category="test_category",
            message="Test message"
        )

        # Should return bool for single event
        assert isinstance(await splunk_connector.send_event(event), bool)

        # Should return int for batch events
        assert isinstance(await splunk_connector.send_events_batch([event]), int)

        # Health check should return dict
        health = await splunk_connector.health_check()
        assert isinstance(health, dict)


if __name__ == "__main__":
    # Run tests if executed directly
    asyncio.run(asyncio.sleep(0))  # Initialize asyncio
    pytest.main([__file__, "-v"])
