import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from resync.api.middleware.csrf_protection import CSRFProtectionMiddleware


class TestCSRFProtection:
    """Testes para o CSRFProtectionMiddleware."""

    @pytest.fixture
    def client(self):
        """Fixture para criar um cliente de teste com o middleware CSRF."""
        app = FastAPI()

        # Configurar o middleware
        middleware = CSRFProtectionMiddleware(app, secret_key="test_secret_key")
        app.add_middleware(CSRFProtectionMiddleware, secret_key="test_secret_key")

        # Rota de teste
        @app.post("/protected")
        async def protected_route():
            return {"status": "protected"}

        @app.get("/public")
        async def public_route():
            return {"status": "public"}

        return TestClient(app)

    @pytest.mark.asyncio
    async def test_protected_route_requires_csrf(self, client):
        """Testar que rota protegida requer token CSRF."""
        response = await client.post("/protected", json={})
        assert response.status_code == 403
        assert "CSRF token validation failed" in response.text

    @pytest.mark.asyncio
    async def test_public_route_does_not_require_csrf(self, client):
        """Testar que rota pública não requer token CSRF."""
        response = await client.get("/public")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_csrf_token_rotation(self, client):
        """Testar rotação de token CSRF após operações de alto risco."""
        # Primeiro acesso para obter token
        response = await client.get("/public")
        assert response.status_code == 200

        # Simular operação de alto risco com token válido
        headers = {"X-CSRF-Token": "test_token"}
        response = await client.post("/protected", headers=headers, json={})

        # Verificar que o token foi rotacionado
        response = await client.post("/protected", headers=headers, json={})
        assert response.status_code == 403
        assert "CSRF token validation failed" in response.text
