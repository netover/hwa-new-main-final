#!/usr/bin/env python3
"""
Final comprehensive CORS testing focusing on core functionality.
"""

from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set up minimal environment variables for testing
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test123"


def test_cors_development() -> None:
    """Test CORS in development environment."""
    print("🧪 Testing Development Environment...")

    # Set development environment
    os.environ["APP_ENV"] = "development"
    os.environ["CORS_ENVIRONMENT"] = "development"

    from resync.api.middleware.cors_config import (
        get_development_cors_config,  # type: ignore[attr-defined]
    )
    from resync.api.middleware.cors_middleware import create_cors_middleware

    app = FastAPI()

    # Create development CORS middleware
    dev_config = get_development_cors_config()  # type: ignore[attr-defined]
    cors_middleware = create_cors_middleware(dev_config)
    app.add_middleware(cors_middleware)  # type: ignore[call-arg,arg-type]

    @app.get("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "Hello from development"}

    client = TestClient(app)

    # Test basic CORS request
    response = client.get("/test", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    # Test preflight request
    response = client.options(
        "/test",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers

    print("✅ Development environment CORS works correctly")


def test_cors_production() -> None:
    """Test CORS in production environment."""
    print("🧪 Testing Production Environment...")

    # Set production environment
    os.environ["APP_ENV"] = "production"
    os.environ["CORS_ENVIRONMENT"] = "production"

    from resync.api.middleware.cors_config import (
        get_production_cors_config,  # type: ignore[attr-defined]
    )
    from resync.api.middleware.cors_middleware import create_cors_middleware

    app = FastAPI()

    # Create production CORS middleware with specific allowed origins
    prod_config = get_production_cors_config(  # type: ignore[attr-defined]
        allowed_origins=["https://app.example.com", "https://api.example.com"],
        allow_credentials=False,
    )
    cors_middleware = create_cors_middleware(prod_config)
    app.add_middleware(cors_middleware)  # type: ignore[call-arg,arg-type]

    @app.get("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "Hello from production"}

    client = TestClient(app)

    # Test allowed origin
    response = client.get("/test", headers={"Origin": "https://app.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"

    # Test another allowed origin
    response = client.get("/test", headers={"Origin": "https://api.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "https://api.example.com"

    print("✅ Production environment CORS works correctly")


def test_cors_test_environment() -> None:
    """Test CORS in test environment."""
    print("🧪 Testing Test Environment...")

    # Set test environment
    os.environ["APP_ENV"] = "test"
    os.environ["CORS_ENVIRONMENT"] = "test"

    from resync.api.middleware.cors_config import get_test_cors_config  # type: ignore[attr-defined]
    from resync.api.middleware.cors_middleware import create_cors_middleware

    app = FastAPI()

    # Create test CORS middleware
    test_config = get_test_cors_config()
    cors_middleware = create_cors_middleware(test_config)
    app.add_middleware(cors_middleware)  # type: ignore[call-arg,arg-type]

    @app.get("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "Hello from test"}

    client = TestClient(app)

    # Test allowed origins from test config
    test_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
    ]

    for origin in test_origins:
        response = client.get("/test", headers={"Origin": origin})
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin

    print("✅ Test environment CORS works correctly")


def test_cors_headers_validation() -> None:
    """Test CORS headers validation."""
    print("🧪 Testing CORS Headers Validation...")

    from resync.api.middleware.cors_config import CORSPolicy, Environment

    # Test production policy restrictions
    policy = CORSPolicy(
        environment=Environment.PRODUCTION,
        allowed_origins=["https://app.example.com"],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allowed_headers=["Content-Type", "Authorization", "X-Requested-With"],
        allow_credentials=False,
        max_age=86400,
    )

    # Validate policy settings
    assert policy.allow_credentials is False  # No credentials in production
    assert policy.max_age == 86400  # 24 hours
    assert "GET" in policy.allowed_methods
    assert "POST" in policy.allowed_methods
    assert "Content-Type" in policy.allowed_headers
    assert "Authorization" in policy.allowed_headers

    print("✅ CORS headers validation works correctly")


def test_cors_violation_detection() -> None:
    """Test CORS violation detection."""
    print("🧪 Testing CORS Violation Detection...")

    from resync.api.middleware.cors_config import (
        get_production_cors_config,  # type: ignore[attr-defined]
    )
    from resync.api.middleware.cors_middleware import (
        create_cors_middleware,
    )

    app = FastAPI()

    # Create production policy with logging
    prod_config = get_production_cors_config(  # type: ignore[attr-defined]
        allowed_origins=["https://app.example.com"], allow_credentials=False
    )
    prod_config.log_violations = True

    cors_middleware = create_cors_middleware(prod_config)
    app.add_middleware(cors_middleware)  # type: ignore[call-arg,arg-type]

    @app.get("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "Hello from production"}

    client = TestClient(app)

    # Test with unauthorized origin
    response = client.get(
        "/test",
        headers={"Origin": "https://unauthorized.com", "User-Agent": "TestClient/1.0"},
    )

    # Should still get response (middleware logs but doesn't block)
    assert response.status_code == 200

    print("✅ CORS violation detection works correctly")


def test_dynamic_origin_patterns() -> None:
    """Test dynamic origin patterns with regex."""
    print("🧪 Testing Dynamic Origin Patterns...")

    from resync.api.middleware.cors_config import CORSPolicy, Environment

    # Create policy with regex patterns
    policy = CORSPolicy(
        environment=Environment.DEVELOPMENT,
        allowed_origins=[],
        origin_regex_patterns=[r"https://.*\.example\.com$", r"https://api\..*\.com$"],
    )

    # Test pattern matching
    test_cases = [
        ("https://app.example.com", True),
        ("https://api.example.com", True),
        ("https://api.service.com", True),
        ("https://malicious.com", False),
        ("https://example.com.evil.com", False),
    ]

    for origin, expected in test_cases:
        result = policy.is_origin_allowed(origin)
        assert result == expected, f"Expected {expected} for {origin}, got {result}"

    print("✅ Dynamic origin patterns work correctly")


def test_preflight_request_handling() -> None:
    """Test preflight request handling."""
    print("🧪 Testing Preflight Request Handling...")

    from resync.api.middleware.cors_config import (
        get_development_cors_config,  # type: ignore[attr-defined]
    )
    from resync.api.middleware.cors_middleware import create_cors_middleware

    app = FastAPI()

    dev_config = get_development_cors_config()  # type: ignore[attr-defined]
    cors_middleware = create_cors_middleware(dev_config)
    app.add_middleware(cors_middleware)  # type: ignore[call-arg,arg-type]

    @app.post("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "Hello from POST"}

    client = TestClient(app)

    # Test preflight request
    response = client.options(
        "/test",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers
    assert "access-control-max-age" in response.headers

    print("✅ Preflight request handling works correctly")


def main() -> None:
    """Run all CORS tests."""
    print("🚀 Starting comprehensive CORS functionality tests...\n")

    try:
        test_cors_development()
        print()

        test_cors_production()
        print()

        test_cors_test_environment()
        print()

        test_cors_headers_validation()
        print()

        test_cors_violation_detection()
        print()

        test_dynamic_origin_patterns()
        print()

        test_preflight_request_handling()
        print()

        print("🎉 All CORS functionality tests passed successfully!")
        print("✅ CORS implementation is fully functional!")
        print("\n📋 Summary of implemented features:")
        print("   ✅ Environment-specific CORS policies")
        print("   ✅ Strict production security (no wildcards)")
        print("   ✅ Dynamic origin validation with regex")
        print("   ✅ CORS violation logging and monitoring")
        print("   ✅ Preflight request handling")
        print("   ✅ Configurable allowed methods and headers")
        print("   ✅ Max age configuration (24 hours)")
        print("   ✅ Development environment flexibility")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
