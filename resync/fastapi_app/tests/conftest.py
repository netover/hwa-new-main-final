
import pytest
from fastapi.testclient import TestClient
import resync.fastapi_app.main as main_module

@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app"""
    with TestClient(main_module.app) as c:
        yield c

@pytest.fixture(scope="module")
def auth_headers():
    """Provide authentication headers for protected endpoints"""
    # This is a placeholder for actual authentication
    # In a real implementation, this would return valid auth tokens
    return {"Authorization": "Bearer test-token"}
