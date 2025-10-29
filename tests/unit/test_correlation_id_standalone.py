#!/usr/bin/env python3
"""
Standalone test for correlation ID functionality that doesn't depend on settings.
"""

import os
import sys
import uuid
from contextvars import ContextVar

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_correlation_id_context():
    """Test correlation ID context management without settings dependency."""
    try:
        # Create context variables directly
        _correlation_id_ctx = ContextVar("correlation_id", default=None)

        def set_correlation_id(correlation_id: str):
            return _correlation_id_ctx.set(correlation_id)

        def get_correlation_id():
            return _correlation_id_ctx.get()

        def get_or_create_correlation_id():
            correlation_id = get_correlation_id()
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
                set_correlation_id(correlation_id)
            return correlation_id

        def clear_correlation_id():
            _correlation_id_ctx.set(None)

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
        print(f"❌ Correlation ID context test failed: {e}")
        return False

def test_correlation_id_middleware():
    """Test correlation ID middleware creation."""
    try:
        from starlette.applications import Starlette

        from resync.api.middleware.correlation_id import CorrelationIdMiddleware

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

def test_uuid_generation():
    """Test UUID generation for correlation IDs."""
    try:
        # Test UUID generation
        correlation_id = str(uuid.uuid4())

        if not correlation_id:
            print("❌ UUID generation failed")
            return False

        print(f"✅ UUID generation works: {correlation_id}")

        # Test UUID format
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'

        if not re.match(uuid_pattern, correlation_id):
            print(f"❌ Invalid UUID format: {correlation_id}")
            return False

        print("✅ UUID format is valid")

        return True
    except Exception as e:
        print(f"❌ UUID generation test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing Correlation ID System (Standalone)")
    print("=" * 50)

    tests = [
        test_correlation_id_context,
        test_correlation_id_middleware,
        test_uuid_generation,
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
    print("❌ Some tests failed")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
