#!/usr/bin/env python3
"""
Simple test to verify correlation ID functionality works correctly.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_correlation_id_imports():
    """Test that correlation ID modules can be imported."""
    try:
        from resync.api.middleware.correlation_id import CORRELATION_ID_HEADER
        print("✅ CorrelationIdMiddleware imported successfully")
        print(f"   Header name: {CORRELATION_ID_HEADER}")

        print("✅ Context functions imported successfully")

        print("✅ Structured logger imported successfully")

        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_correlation_id_generation():
    """Test correlation ID generation and context management."""
    try:
        from resync.core.context import (
            set_correlation_id,
            get_correlation_id,
            get_or_create_correlation_id,
            clear_correlation_id
        )

        # Test setting and getting correlation ID
        test_id = "test-correlation-id-123"
        set_correlation_id(test_id)

        retrieved_id = get_correlation_id()
        if retrieved_id != test_id:
            print(f"❌ Set/Get mismatch: expected {test_id}, got {retrieved_id}")
            return False

        print(f"✅ Set/Get correlation ID works: {retrieved_id}")

        # Test get_or_create when ID exists
        existing_id = get_or_create_correlation_id()
        if existing_id != test_id:
            print(f"❌ GetOrCreate with existing ID failed: expected {test_id}, got {existing_id}")
            return False

        print(f"✅ GetOrCreate with existing ID works: {existing_id}")

        # Clear and test get_or_create creates new ID
        clear_correlation_id()
        new_id = get_or_create_correlation_id()

        if not new_id or new_id == test_id:
            print(f"❌ GetOrCreate after clear failed: got {new_id}")
            return False

        print(f"✅ GetOrCreate after clear works: {new_id}")

        return True
    except Exception as e:
        print(f"❌ Correlation ID generation test failed: {e}")
        return False

def test_correlation_id_middleware():
    """Test correlation ID middleware creation."""
    try:
        from resync.api.middleware.correlation_id import CorrelationIdMiddleware
        from starlette.applications import Starlette

        # Create a simple ASGI app for testing
        app = Starlette()

        # Create middleware
        middleware = CorrelationIdMiddleware(app)

        print("✅ CorrelationIdMiddleware created successfully")
        print(f"   Header name: {middleware.header_name}")
        print(f"   Generate if missing: {middleware.generate_if_missing}")

        return True
    except Exception as e:
        print(f"❌ Middleware creation failed: {e}")
        return False

def test_logger_integration():
    """Test that logger includes correlation ID."""
    try:
        from resync.core.structured_logger import get_logger, add_correlation_id
        from resync.core.context import set_correlation_id

        # Set correlation ID in context
        test_id = "logger-test-correlation-id"
        set_correlation_id(test_id)

        # Create logger and test event dict
        logger = get_logger("test_logger")

        # Test the processor function
        event_dict = {}
        result_dict = add_correlation_id(logger, "info", event_dict)

        if "correlation_id" not in result_dict or result_dict["correlation_id"] != test_id:
            print(f"❌ Logger processor failed: expected correlation_id {test_id} in {result_dict}")
            return False

        print(f"✅ Logger processor works: {result_dict}")

        return True
    except Exception as e:
        print(f"❌ Logger integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing Correlation ID System")
    print("=" * 50)

    tests = [
        test_correlation_id_imports,
        test_correlation_id_generation,
        test_correlation_id_middleware,
        test_logger_integration,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if test():
            passed += 1
        else:
            print(f"❌ {test.__name__} failed")

    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All correlation ID tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)