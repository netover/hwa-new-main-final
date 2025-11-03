import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from resync.core.teams_integration import (
    TeamsConfig,
    TeamsIntegration,
    TeamsNotification,
)


async def test_teams_integration():
    print("Testing Teams integration...")

    # Create Teams integration with test configuration
    config = TeamsConfig(
        enabled=False,
        webhook_url="https://test.webhook.office.com/webhook",
        channel_name="Test Channel",
        bot_name="Test Bot",
    )

    teams_integration = TeamsIntegration(config)
    print("TeamsIntegration created successfully")

    # Test notification formatting
    notification = TeamsNotification(
        title="Test Notification",
        message="This is a test message",
        severity="info",
        job_id="TEST123",
        job_status="ABEND",
        instance_name="TWS_TEST",
    )

    # Test formatting
    try:
        teams_integration._format_teams_message(notification)
        print("Teams message formatting works")
    except Exception as e:
        print(f"Teams message formatting failed: {e}")
        return False

    # Test health check
    try:
        await teams_integration.health_check()
        print("Health check works")
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

    print("All Teams integration tests passed!")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_teams_integration())
        if result:
            print("SUCCESS: Teams integration is working correctly")
        else:
            print("FAILURE: Teams integration tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"EXCEPTION: {e}")
        sys.exit(1)




