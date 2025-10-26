
from fastapi.testclient import TestClient
import resync.fastapi_app.main as main_module

client = TestClient(main_module.app)

def test_get_audit_flags():
    """Test GET /api/audit/flags endpoint"""
    response = client.get("/api/audit/flags")
    assert response.status_code == 200
    assert "flags" in response.json()

def test_get_audit_metrics():
    """Test GET /api/audit/metrics endpoint"""
    response = client.get("/api/audit/metrics")
    assert response.status_code == 200
    assert "pending" in response.json()
    assert "approved" in response.json()
    assert "rejected" in response.json()

def test_review_audit_flag():
    """Test POST /api/audit/review endpoint"""
    review_data = {
        "memory_id": "test_memory_id",
        "action": "approve"
    }
    response = client.post("/api/audit/review", json=review_data)
    assert response.status_code == 200
    assert "memory_id" in response.json()
    assert "action" in response.json()
    assert "status" in response.json()
