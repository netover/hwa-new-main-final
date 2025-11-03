"""Test for Microsoft Teams integration."""

from unittest.mock import AsyncMock, patch

import pytest

from resync.core.teams_integration import (
    TeamsConfig,
    TeamsIntegration,
    TeamsNotification,
)


@pytest.mark.asyncio
async def test_teams_integration_initialization():
    """Test Teams integration initialization."""
    # Test with default config
    teams_integration = TeamsIntegration()
    assert teams_integration is not None
    assert isinstance(teams_integration.config, TeamsConfig)

    # Test with custom config
    custom_config = TeamsConfig(
        enabled=True,
        webhook_url="https://test.webhook.office.com/webhook",
        channel_name="Test Channel",
        bot_name="Test Bot",
    )
    teams_integration_custom = TeamsIntegration(custom_config)
    assert teams_integration_custom.config == custom_config


@pytest.mark.asyncio
async def test_teams_notification_formatting():
    """Test Teams notification formatting."""
    teams_integration = TeamsIntegration()

    # Create a test notification
    notification = TeamsNotification(
        title="Test Notification",
        message="This is a test message",
        severity="info",
        job_id="TEST123",
        job_status="ABEND",
        instance_name="TWS_TEST",
        additional_data={"test_key": "test_value"},
    )

    # Format the notification
    formatted_message = teams_integration._format_teams_message(notification)

    # Verify the structure
    assert "type" in formatted_message
    assert "attachments" in formatted_message
    assert len(formatted_message["attachments"]) > 0

    attachment = formatted_message["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert "content" in attachment

    content = attachment["content"]
    assert content["type"] == "AdaptiveCard"
    assert "version" in content
    assert "body" in content

    # Verify title and message are in the body
    body_items = content["body"]
    assert any(
        item.get("text") == "Test Notification" for item in body_items if "text" in item
    )
    assert any(
        item.get("text") == "This is a test message"
        for item in body_items
        if "text" in item
    )


@pytest.mark.asyncio
async def test_teams_send_notification_disabled():
    """Test sending notification when Teams integration is disabled."""
    config = TeamsConfig(enabled=False)
    teams_integration = TeamsIntegration(config)

    notification = TeamsNotification(title="Test", message="Test message")

    # Should return False when disabled
    result = await teams_integration.send_notification(notification)
    assert result is False


@pytest.mark.asyncio
async def test_teams_send_notification_no_webhook():
    """Test sending notification when no webhook URL is configured."""
    config = TeamsConfig(enabled=True, webhook_url=None)
    teams_integration = TeamsIntegration(config)

    notification = TeamsNotification(title="Test", message="Test message")

    # Should raise NotificationError when no webhook URL
    with pytest.raises(Exception):  # Using generic Exception since it might be wrapped
        await teams_integration.send_notification(notification)


@patch("aiohttp.ClientSession")
@pytest.mark.asyncio
async def test_teams_send_notification_success(mock_session_class):
    """Test successful notification sending."""
    # Setup mock session
    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value.status = 200
    mock_session_class.return_value = mock_session

    # Setup Teams integration
    config = TeamsConfig(
        enabled=True, webhook_url="https://test.webhook.office.com/webhook"
    )
    teams_integration = TeamsIntegration(config)

    # Create notification
    notification = TeamsNotification(title="Test Success", message="Test message")

    # Send notification
    result = await teams_integration.send_notification(notification)

    # Verify success
    assert result is True
    mock_session.post.assert_called_once()


@patch("aiohttp.ClientSession")
@pytest.mark.asyncio
async def test_teams_send_notification_failure(mock_session_class):
    """Test failed notification sending."""
    # Setup mock session to return error status
    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value.status = 500
    mock_session_class.return_value = mock_session

    # Setup Teams integration
    config = TeamsConfig(
        enabled=True, webhook_url="https://test.webhook.office.com/webhook"
    )
    teams_integration = TeamsIntegration(config)

    # Create notification
    notification = TeamsNotification(title="Test Failure", message="Test message")

    # Send notification
    result = await teams_integration.send_notification(notification)

    # Verify failure
    assert result is False
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_teams_health_check():
    """Test Teams integration health check."""
    teams_integration = TeamsIntegration()

    # Perform health check
    health_status = await teams_integration.health_check()

    # Verify health status structure
    assert isinstance(health_status, dict)
    assert "enabled" in health_status
    assert "configured" in health_status
    assert "conversation_learning" in health_status
    assert "job_notifications" in health_status


@pytest.mark.asyncio
async def test_teams_job_monitoring():
    """Test job status monitoring."""
    # Setup Teams integration with job notifications enabled
    config = TeamsConfig(
        enabled=True,
        enable_job_notifications=True,
        job_status_filters=["ABEND", "ERROR"],
    )
    teams_integration = TeamsIntegration(config)

    # Mock the send_notification method
    teams_integration.send_notification = AsyncMock(return_value=True)

    # Test job data that should trigger notification
    job_data = {
        "job_name": "TEST_JOB",
        "job_id": "TEST123",
        "status": "ABEND",
        "start_time": "2023-01-01T10:00:00Z",
        "end_time": "2023-01-01T10:05:00Z",
        "duration": "5 minutes",
        "owner": "test_user",
    }

    # Monitor job status
    await teams_integration.monitor_job_status(job_data, "TWS_TEST")

    # Verify notification was sent
    teams_integration.send_notification.assert_called_once()


@pytest.mark.asyncio
async def test_teams_conversation_learning():
    """Test conversation learning from Teams."""
    teams_integration = TeamsIntegration()

    # Test learning from conversation
    test_message = "This is a test conversation message"
    context = {"sender": "test_user", "timestamp": "2023-01-01T10:00:00Z"}

    # Should not raise exception
    await teams_integration.learn_from_conversation(test_message, context)

    # Test when conversation learning is enabled
    config = TeamsConfig(enabled=True, enable_conversation_learning=True)
    teams_integration_with_learning = TeamsIntegration(config)

    # Should not raise exception
    await teams_integration_with_learning.learn_from_conversation(test_message, context)


if __name__ == "__main__":
    pytest.main([__file__])




