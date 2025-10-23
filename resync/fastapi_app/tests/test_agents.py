
import pytest
from fastapi.testclient import TestClient
import resync.fastapi_app.main as main_module

client = TestClient(main_module.app)

def test_list_agents():
    """Test GET /api/ endpoint"""
    response = client.get("/api/")
    assert response.status_code == 200
    assert "agents" in response.json()

def test_get_agent_status():
    """Test GET /api/status endpoint"""
    response = client.get("/api/status", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert "workstations" in response.json()
    assert "jobs" in response.json()
