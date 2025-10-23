#!/usr/bin/env python3
"""
Test runner for health check tests with proper environment setup.
"""

import os
import sys
from pathlib import Path


def setup_test_environment():
    """Set up the test environment variables."""
    # Set required environment variables
    os.environ["APP_ENV"] = "test"
    os.environ["ADMIN_USERNAME"] = "test_admin"
    os.environ["ADMIN_PASSWORD"] = "test_password123"
    os.environ["DATABASE_URL"] = "sqlite:///./test_health.db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["DEBUG"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["HEALTH_CHECK_ENABLED"] = "true"
    os.environ["HEALTH_CHECK_INTERVAL"] = "30"

    print("✅ Test environment configured")


def run_tests():
    """Run the health check tests."""
    try:
        # Import and run tests directly
        import pytest

        # Change to testbed directory if needed
        testbed_dir = Path(__file__).parent
        os.chdir(testbed_dir)

        # Run pytest with specific test file
        result = pytest.main(
            ["tests/test_health_checks.py", "-v", "--tb=short", "--log-level=INFO"]
        )

        return result

    except ImportError as e:
        print(f"❌ Error importing pytest: {e}")
        return 1
    except (ModuleNotFoundError, FileNotFoundError, RuntimeError) as e:
        print(f"❌ Error running tests: {e}")
        return 1


def main():
    """Main function."""
    print("🚀 Starting health check tests...")

    # Setup environment
    setup_test_environment()

    # Run tests
    result = run_tests()

    if result == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ Tests failed with exit code: {result}")

    return result


if __name__ == "__main__":
    sys.exit(main())
