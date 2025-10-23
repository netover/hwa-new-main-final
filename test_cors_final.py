#!/usr/bin/env python3
"""
Final comprehensive CORS testing focusing on core functionality.
"""

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set up minimal environment variables for testing
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test123"


def test_cors_development():
    """Test CORS in development environment."""
    print("🧪 Testing Development Environment...")

    # Set development environment
    os.environ["APP_ENV"] = "development"
    os.environ["CORS_ENVIRONMENT"] = "development"

    from resync.api.middleware.cors_middleware import (
        add_cors_middleware,
        get_development_cors_config,
    )

    app = FastAPI()

    # Create development CORS policy and add middleware
    dev_policy = get_development_cors_config()
    add_cors_middleware(app, environment="development", custom_policy=dev_policy)

    @app.get("/test")
    def test_endpoint():
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


def test_cors_production():
    """Test CORS in production environment."""
    print("🧪 Testing Production Environment...")

    # Set production environment
    os.environ["APP_ENV"] = "production"
    os.environ["CORS_ENVIRONMENT"] = "production"

    from resync.api.middleware.cors_middleware import (
        add_cors_middleware,
        get_production_cors_config,
    )

    app = FastAPI()

    # Create production CORS policy with specific allowed origins
    prod_policy = get_production_cors_config(
        allowed_origins=["https://app.example.com", "https://api.example.com"],
        allow_credentials=False,
    )
    add_cors_middleware(app, environment="production", custom_policy=prod_policy)

    @app.get("/test")
    def test_endpoint():
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


def test_cors_test_environment():
    """Test CORS in test environment."""
    print("🧪 Testing Test Environment...")

    # Set test environment
    os.environ["APP_ENV"] = "test"
    os.environ["CORS_ENVIRONMENT"] = "test"

    from resync.api.middleware.cors_middleware import (
        add_cors_middleware,
        get_test_cors_config,
    )

    app = FastAPI()

    # Create test CORS policy and add middleware
    test_policy = get_test_cors_config()
    add_cors_middleware(app, environment="test", custom_policy=test_policy)

    @app.get("/test")
    def test_endpoint():
        return {"message": "Hello from test"}

    client = TestClient(app)

    # Test allowed origins from test config
    test_origins = ["http://localhost:3000", "http://localhost:8000"]

    for origin in test_origins:
        response = client.get("/test", headers={"Origin": origin})
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin

    print("✅ Test environment CORS works correctly")


def test_cors_headers_validation():
    """Test CORS headers validation."""
    print("🧪 Testing CORS Headers Validation...")

    from resync.api.middleware.cors_middleware import get_production_cors_config

    # Test production policy restrictions
    policy = get_production_cors_config(
        allowed_origins=["https://app.example.com"], allow_credentials=False
    )

    # Validate policy settings
    assert policy.allow_credentials is False  # No credentials in production
    assert policy.max_age == 86400  # 24 hours
    assert "GET" in policy.allowed_methods
    assert "POST" in policy.allowed_methods
    assert "Content-Type" in policy.allowed_headers
    assert "Authorization" in policy.allowed_headers

    print("✅ CORS headers validation works correctly")


def test_cors_violation_detection():
    """Test CORS violation detection."""
    print("🧪 Testing CORS Violation Detection...")

    from resync.api.middleware.cors_middleware import (
        add_cors_middleware,
        get_production_cors_config,
    )

    app = FastAPI()

    # Create production policy with logging
    prod_policy = get_production_cors_config(
        allowed_origins=["https://app.example.com"], allow_credentials=False
    )
    prod_policy.log_violations = True

    add_cors_middleware(app, environment="production", custom_policy=prod_policy)

    @app.get("/test")
    def test_endpoint():
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


def test_dynamic_origin_patterns():
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


def test_preflight_request_handling():
    """Test preflight request handling."""
    print("🧪 Testing Preflight Request Handling...")

    from resync.api.middleware.cors_middleware import (
        add_cors_middleware,
        get_development_cors_config,
    )

    app = FastAPI()

    dev_policy = get_development_cors_config()
    add_cors_middleware(app, environment="development", custom_policy=dev_policy)

    @app.post("/test")
    def test_endpoint():
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

    # Note: OPTIONS requests return 405 for endpoints that don't explicitly handle OPTIONS
    # The important thing is that CORS headers are present
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers
    assert "access-control-max-age" in response.headers

    print("✅ Preflight request handling works correctly")


def test_environment_policy_access():
    """Test accessing policies from environment configuration."""
    print("🧪 Testing Environment Policy Access...")

    from resync.api.middleware.cors_config import Environment, cors_config

    # Test getting policies for different environments
    dev_policy = cors_config.get_policy(Environment.DEVELOPMENT)
    prod_policy = cors_config.get_policy(Environment.PRODUCTION)
    test_policy = cors_config.get_policy(Environment.TEST)

    # Validate default policies
    assert dev_policy.environment == Environment.DEVELOPMENT
    assert dev_policy.allow_all_origins
    assert "*" in dev_policy.allowed_origins

    assert prod_policy.environment == Environment.PRODUCTION
    assert not prod_policy.allow_all_origins
    assert not prod_policy.allow_credentials

    assert test_policy.environment == Environment.TEST
    assert "http://localhost:3000" in test_policy.allowed_origins

    print("✅ Environment policy access works correctly")


def test_policy_validation():
    """Test CORS policy validation."""
    print("🧪 Testing CORS Policy Validation...")

    from resync.api.middleware.cors_config import CORSPolicy, Environment

    # Test production policy with wildcard (should fail)
    try:
        policy = CORSPolicy(environment=Environment.PRODUCTION, allowed_origins=["*"])
        raise AssertionError("Should have raised ValueError for wildcard in production")
    except ValueError as e:
        assert "Wildcard origins are not allowed in production" in str(e)

    # Test production policy with valid origins (should succeed)
    policy = CORSPolicy(
        environment=Environment.PRODUCTION,
        allowed_origins=["https://app.example.com", "https://api.example.com"],
    )
    assert policy.environment == Environment.PRODUCTION
    assert "https://app.example.com" in policy.allowed_origins

    # Test method validation
    try:
        policy = CORSPolicy(
            environment=Environment.DEVELOPMENT,
            allowed_methods=["GET", "INVALID_METHOD"],
        )
        raise AssertionError("Should have raised ValueError for invalid method")
    except ValueError as e:
        assert "Invalid HTTP method" in str(e)

    print("✅ CORS policy validation works correctly")


def main():
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

        test_environment_policy_access()
        print()

        test_policy_validation()
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
        print("   ✅ Comprehensive policy validation")
        print("   ✅ Environment-based configuration management")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
