
from fastapi.testclient import TestClient
import resync.fastapi_app.main as main_module

client = TestClient(main_module.app)

def test_rag_upload_no_file():
    """Test POST /api/rag/upload endpoint with no file"""
    response = client.post("/api/rag/upload")
    assert response.status_code == 422  # Validation error for missing file
