import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def read_root():
        return "<html><body>Hello, World!</body></html>"

    return TestClient(app)


def test_simple_html_response(client: TestClient):
    """Test a simple HTML response."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "<html><body>Hello, World!</body></html>"




