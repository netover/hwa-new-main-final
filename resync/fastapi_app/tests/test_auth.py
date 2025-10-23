
import pytest
from fastapi.testclient import TestClient
import resync.fastapi_app.main as main_module
from ..api.v1.models.request_models import LoginRequest

client = TestClient(main_module.app)

def test_login_get():
    """Test GET /api/auth/login endpoint"""
    response = client.get("/api/auth/login")
    assert response.status_code == 200
    assert "message" in response.json()

def test_login_post():
    """Test POST /api/auth/login endpoint"""
    login_data = {
        "username": "testuser",
        "password": "testpass"
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    assert "message" in response.json()

def test_login_post_invalid():
    """Test POST /api/auth/login with invalid data"""
    # Missing required fields
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 422  # Validation error
