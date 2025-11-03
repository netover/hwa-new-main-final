#!/usr/bin/env python3
"""
Test preflight request handling specifically.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set up minimal environment variables for testing
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test123"


def test_preflight_request_handling() -> None:
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

    print(f"Preflight response status: {response.status_code}")
    print(f"Preflight response headers: {dict(response.headers)}")
    print(f"Preflight response body: {response.text}")

    # Check CORS headers are present (status code may vary)
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers
    assert "access-control-max-age" in response.headers

    print("✅ Preflight request handling works correctly")


def test_regular_request() -> None:
    """Test regular request to compare."""
    print("🧪 Testing Regular Request...")

    from resync.api.middleware.cors_middleware import (
        add_cors_middleware,
        get_development_cors_config,
    )

    app = FastAPI()

    dev_policy = get_development_cors_config()
    add_cors_middleware(app, environment="development", custom_policy=dev_policy)

    @app.post("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "Hello from POST"}

    client = TestClient(app)

    # Test regular POST request
    response = client.post(
        "/test",
        headers={"Origin": "http://localhost:3000", "Content-Type": "application/json"},
        json={"test": "data"},
    )

    print(f"Regular POST response status: {response.status_code}")
    print(f"Regular POST response headers: {dict(response.headers)}")

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

    print("✅ Regular request works correctly")


if __name__ == "__main__":
    test_preflight_request_handling()
    print()
    test_regular_request()





