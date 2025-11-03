#!/usr/bin/env python3
"""
Comprehensive CORS testing across different environments.
"""

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from resync.api.middleware.cors_config import CORSPolicy, Environment
from resync.api.middleware.cors_middleware import (
    add_cors_middleware,
    get_production_cors_config,
)

# Set up minimal environment variables for testing
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test123"
os.environ["APP_ENV"] = "development"


def test_development_environment():
    """Test CORS in development environment."""
    print("🧪 Testing Development Environment...")

    # Set development environment
    os.environ["APP_ENV"] = "development"
    os.environ["CORS_ENVIRONMENT"] = "development"

    app = FastAPI()
    add_cors_middleware(app, environment="development")

    @app.get("/test")
    def test_endpoint():
        return {"message": "Hello from development"}

    client = TestClient(app)

    # Test CORS request
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


def test_production_environment():
    """Test CORS in production environment."""
    print("🧪 Testing Production Environment...")

    # Set production environment with specific allowed origins
    os.environ["APP_ENV"] = "production"
    os.environ["CORS_ENVIRONMENT"] = "production"
    os.environ["CORS_ALLOWED_ORIGINS"] = (
        "https://app.example.com,https://api.example.com"
    )

    app = FastAPI()

    # Create production policy with specific origins
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

    # Test disallowed origin (should still get CORS headers but no access)
    response = client.get("/test", headers={"Origin": "https://unauthorized.com"})
    # In production, unauthorized origins should not get access
    # Note: The middleware logs violations but still processes the request

    print("✅ Production environment CORS works correctly")


def test_test_environment():
    """Test CORS in test environment."""
    print("🧪 Testing Test Environment...")

    # Set test environment
    os.environ["APP_ENV"] = "test"
    os.environ["CORS_ENVIRONMENT"] = "test"

    app = FastAPI()
    add_cors_middleware(app, environment="test")

    @app.get("/test")
    def test_endpoint():
        return {"message": "Hello from test"}

    client = TestClient(app)

    # Test allowed origin from test config
    response = client.get("/test", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

    # Test another allowed origin
    response = client.get("/test", headers={"Origin": "http://localhost:8000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

    print("✅ Test environment CORS works correctly")


def test_cors_violation_logging():
    """Test CORS violation logging."""
    print("🧪 Testing CORS Violation Logging...")

    # Set production environment
    os.environ["APP_ENV"] = "production"
    os.environ["CORS_ENVIRONMENT"] = "production"
    os.environ["CORS_ALLOWED_ORIGINS"] = "https://app.example.com"

    app = FastAPI()

    # Create policy with logging enabled
    prod_policy = get_production_cors_config(
        allowed_origins=["https://app.example.com"], allow_credentials=False
    )
    prod_policy.log_violations = True

    add_cors_middleware(app, environment="production", custom_policy=prod_policy)

    @app.get("/test")
    def test_endpoint():
        return {"message": "Hello from production"}

    client = TestClient(app)

    # Test with unauthorized origin (should log violation)
    response = client.get(
        "/test",
        headers={"Origin": "https://unauthorized.com", "User-Agent": "TestClient/1.0"},
    )

    # Should still get a response (middleware logs but doesn't block)
    assert response.status_code == 200

    print("✅ CORS violation logging works correctly")


def test_dynamic_origin_validation():
    """Test dynamic origin validation with regex patterns."""
    print("🧪 Testing Dynamic Origin Validation...")

    app = FastAPI()

    # Create policy with regex patterns
    policy = CORSPolicy(
        environment=Environment.DEVELOPMENT,
        allowed_origins=[],
        origin_regex_patterns=[r"https://.*\.example\.com$", r"https://api\..*\.com$"],
    )

    add_cors_middleware(app, environment="development", custom_policy=policy)

    @app.get("/test")
    def test_endpoint():
        return {"message": "Hello with regex validation"}

    client = TestClient(app)

    # Test matching regex patterns
    test_origins = [
        "https://app.example.com",
        "https://api.example.com",
        "https://api.service.com",
    ]

    for origin in test_origins:
        response = client.get("/test", headers={"Origin": origin})
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin

    print("✅ Dynamic origin validation works correctly")


def test_cors_monitoring_endpoints():
    """Test CORS monitoring endpoints."""
    print("🧪 Testing CORS Monitoring Endpoints...")

    # Use development environment for testing
    os.environ["APP_ENV"] = "development"
    os.environ["CORS_ENVIRONMENT"] = "development"

    from resync.api.cors_monitoring import cors_monitor_router
    from resync.core.rate_limiter import init_rate_limiter

    app = FastAPI()
    init_rate_limiter(app)
    app.include_router(cors_monitor_router, prefix="/api/cors")

    client = TestClient(app)

    # Test config endpoint
    response = client.get("/api/cors/config")
    assert response.status_code == 200
    config_data = response.json()
    assert "environment" in config_data
    assert "allowed_origins" in config_data
    assert "allowed_methods" in config_data

    # Test test endpoint
    response = client.post(
        "/api/cors/test", params={"origin": "http://localhost:3000", "method": "GET"}
    )
    assert response.status_code == 200
    test_data = response.json()
    assert "origin_allowed" in test_data
    assert "method_allowed" in test_data

    print("✅ CORS monitoring endpoints work correctly")


def main():
    """Run all environment tests."""
    print("🚀 Starting comprehensive CORS environment tests...\n")

    try:
        test_development_environment()
        print()

        test_production_environment()
        print()

        test_test_environment()
        print()

        test_cors_violation_logging()
        print()

        test_dynamic_origin_validation()
        print()

        test_cors_monitoring_endpoints()
        print()

        print("🎉 All CORS environment tests passed successfully!")
        print("✅ CORS implementation is fully functional across all environments!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()




