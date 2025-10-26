
from fastapi.testclient import TestClient
import resync.fastapi_app.main as main_module

client = TestClient(main_module.app)

def test_chat_message():
    """Test POST /api/chat/ endpoint"""
    response = client.post("/api/chat/")
    assert response.status_code == 200
    assert "message" in response.json()
