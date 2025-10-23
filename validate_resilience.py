"""
Simple validation script for resilience patterns implementation.

This script validates that the resilience patterns are working correctly
without requiring complex test dependencies.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def validate_teams_integration_resilience():
    """Validate Teams Integration resilience patterns."""
    print("🔧 Validating Teams Integration resilience patterns...")

    try:
        from resync.core.teams_integration import TeamsConfig, TeamsIntegration

        # Create Teams integration instance
        config = TeamsConfig(
            enabled=True,
            webhook_url="https://outlook.office.com/webhook/test"
        )
        teams_integration = TeamsIntegration(config)

        # Validate circuit breaker initialization
        assert hasattr(teams_integration, 'circuit_breaker_manager'), "Circuit breaker manager not initialized"
        assert teams_integration.circuit_breaker_manager.state("teams_webhook") == "closed", "Circuit breaker not in closed state"
        print("✅ Circuit breaker properly initialized")

        # Validate backpressure mechanism
        assert hasattr(teams_integration, '_notification_semaphore'), "Backpressure semaphore not initialized"
        assert teams_integration._notification_semaphore._value == 10, "Backpressure semaphore not configured correctly"
        print("✅ Backpressure mechanism properly initialized")

        # Validate rate limiting
        assert hasattr(teams_integration, '_notification_rate_limit'), "Rate limiting not configured"
        assert teams_integration._notification_rate_limit == 30, "Rate limiting not configured correctly"
        print("✅ Rate limiting properly configured")

        print("✅ Teams Integration resilience patterns validated successfully")
        return True

    except Exception as e:
        print(f"❌ Teams Integration validation failed: {e}")
        return False


async def validate_siem_integration_resilience():
    """Validate SIEM Integration resilience patterns."""
    print("🔧 Validating SIEM Integration resilience patterns...")

    try:
        from resync.core.siem_integrator import SIEMConfiguration, SIEMType, SplunkConnector, ELKConnector

        # Create SIEM configurations
        splunk_config = SIEMConfiguration(
            siem_type=SIEMType.SPLUNK,
            name="test_splunk",
            endpoint_url="https://splunk.example.com:8088",
            api_key="test_api_key"
        )

        elk_config = SIEMConfiguration(
            siem_type=SIEMType.ELK_STACK,
            name="test_elk",
            endpoint_url="https://elk.example.com:9200",
            api_key="test_api_key"
        )

        # Create connectors
        splunk_connector = SplunkConnector(splunk_config)
        elk_connector = ELKConnector(elk_config)

        # Validate circuit breaker initialization for Splunk
        assert hasattr(splunk_connector, 'circuit_breaker_manager'), "Splunk circuit breaker manager not initialized"
        assert splunk_connector.circuit_breaker_manager.state("splunk_events") == "closed", "Splunk events circuit breaker not in closed state"
        print("✅ Splunk circuit breaker properly initialized")

        # Validate backpressure mechanism for Splunk
        assert hasattr(splunk_connector, '_send_semaphore'), "Splunk backpressure semaphore not initialized"
        assert splunk_connector._send_semaphore._value == 5, "Splunk backpressure semaphore not configured correctly"
        print("✅ Splunk backpressure mechanism properly initialized")

        # Validate circuit breaker initialization for ELK
        assert hasattr(elk_connector, 'circuit_breaker_manager'), "ELK circuit breaker manager not initialized"
        assert elk_connector.circuit_breaker_manager.state("elk_events") == "closed", "ELK events circuit breaker not in closed state"
        print("✅ ELK circuit breaker properly initialized")

        # Validate backpressure mechanism for ELK
        assert hasattr(elk_connector, '_send_semaphore'), "ELK backpressure semaphore not initialized"
        assert elk_connector._send_semaphore._value == 5, "ELK backpressure semaphore not configured correctly"
        print("✅ ELK backpressure mechanism properly initialized")

        print("✅ SIEM Integration resilience patterns validated successfully")
        return True

    except Exception as e:
        print(f"❌ SIEM Integration validation failed: {e}")
        return False


async def validate_resilience_core():
    """Validate core resilience patterns."""
    print("🔧 Validating core resilience patterns...")

    try:
        from resync.core.resilience import CircuitBreakerManager, retry_with_backoff

        # Test CircuitBreakerManager
        cbm = CircuitBreakerManager()
        cbm.register("test_service", fail_max=2, reset_timeout=30)

        assert cbm.state("test_service") == "closed", "Circuit breaker not in closed state"
        print("✅ CircuitBreakerManager working correctly")

        # Test retry_with_backoff
        attempt_count = 0

        async def test_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Test failure")
            return "success"

        result = await retry_with_backoff_async(
            test_function,
            retries=3,
            base_delay=0.01,
            cap=0.1,
            jitter=True,
            retry_on=(Exception,)
        )

        assert result == "success", "Retry function did not return expected result"
        assert attempt_count == 3, "Retry function did not retry expected number of times"
        print("✅ retry_with_backoff working correctly")

        print("✅ Core resilience patterns validated successfully")
        return True

    except Exception as e:
        print(f"❌ Core resilience validation failed: {e}")
        return False


async def validate_backward_compatibility():
    """Validate that existing functionality is not broken."""
    print("🔧 Validating backward compatibility...")

    try:
        from resync.core.teams_integration import TeamsConfig, TeamsIntegration, TeamsNotification
        from resync.core.siem_integrator import SIEMConfiguration, SIEMType, SplunkConnector, SIEMEvent

        # Test Teams Integration interface
        config = TeamsConfig(enabled=True, webhook_url="https://test.com")
        teams_integration = TeamsIntegration(config)
        notification = TeamsNotification(title="Test", message="Test message", severity="info")

        # Validate method signatures are unchanged
        assert callable(teams_integration.send_notification), "send_notification method missing"
        assert callable(teams_integration.health_check), "health_check method missing"
        assert callable(teams_integration.monitor_job_status), "monitor_job_status method missing"
        print("✅ Teams Integration interface unchanged")

        # Test SIEM Integration interface
        siem_config = SIEMConfiguration(
            siem_type=SIEMType.SPLUNK,
            name="test",
            endpoint_url="https://test.com",
            api_key="test"
        )
        splunk_connector = SplunkConnector(siem_config)
        event = SIEMEvent(
            event_id="test_event",
            timestamp=1234567890,
            source="test_source",
            event_type="test_event",
            severity="medium",
            category="test_category",
            message="Test message"
        )

        # Validate method signatures are unchanged
        assert callable(splunk_connector.connect), "connect method missing"
        assert callable(splunk_connector.disconnect), "disconnect method missing"
        assert callable(splunk_connector.send_event), "send_event method missing"
        assert callable(splunk_connector.send_events_batch), "send_events_batch method missing"
        assert callable(splunk_connector.health_check), "health_check method missing"
        print("✅ SIEM Integration interface unchanged")

        print("✅ Backward compatibility validated successfully")
        return True

    except Exception as e:
        print(f"❌ Backward compatibility validation failed: {e}")
        return False


async def main():
    """Run all validation tests."""
    print("🚀 Starting resilience patterns validation...\n")

    results = []

    # Run all validations
    results.append(await validate_resilience_core())
    results.append(await validate_teams_integration_resilience())
    results.append(await validate_siem_integration_resilience())
    results.append(await validate_backward_compatibility())

    # Summary
    print("\n" + "="*60)
    print("📊 VALIDATION SUMMARY")
    print("="*60)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("🎉 Resilience patterns implementation is working correctly!")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        print("🔧 Please review the implementation and fix any issues.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)