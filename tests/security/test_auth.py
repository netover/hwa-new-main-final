import pytest
from unittest.mock import patch

from resync.api.auth import SecureAuthenticator
from resync.settings import settings


class TestSecureAuthenticator:
    """Testes para o SecureAuthenticator."""

    @pytest.fixture
    def authenticator(self):
        """Fixture para criar uma instância do SecureAuthenticator."""
        return SecureAuthenticator()

    @pytest.mark.asyncio
    async def test_valid_credentials(self, authenticator):
        """Teste de credenciais válidas."""
        # Configurar credenciais de teste no settings
        with (
            patch.object(settings, "admin_username", "testadmin"),
            patch.object(settings, "admin_password", "testpassword"),
            patch.object(settings, "secret_key", "testsecretkey"),
        ):

            result, error = await authenticator.verify_credentials(
                username="testadmin", password="testpassword", request_ip="127.0.0.1"
            )

            assert result is True
            assert error is None

    @pytest.mark.asyncio
    async def test_invalid_username(self, authenticator):
        """Teste de nome de usuário inválido."""
        with (
            patch.object(settings, "admin_username", "testadmin"),
            patch.object(settings, "admin_password", "testpassword"),
            patch.object(settings, "secret_key", "testsecretkey"),
        ):

            result, error = await authenticator.verify_credentials(
                username="wronguser", password="testpassword", request_ip="127.0.0.1"
            )

            assert result is False
            assert "Invalid credentials" in error

    @pytest.mark.asyncio
    async def test_invalid_password(self, authenticator):
        """Teste de senha inválida."""
        with (
            patch.object(settings, "admin_username", "testadmin"),
            patch.object(settings, "admin_password", "testpassword"),
            patch.object(settings, "secret_key", "testsecretkey"),
        ):

            result, error = await authenticator.verify_credentials(
                username="testadmin", password="wrongpassword", request_ip="127.0.0.1"
            )

            assert result is False
            assert "Invalid credentials" in error

    @pytest.mark.asyncio
    async def test_ip_lockout(self, authenticator):
        """Teste de bloqueio de IP após múltiplas tentativas inválidas."""
        with (
            patch.object(settings, "admin_username", "testadmin"),
            patch.object(settings, "admin_password", "testpassword"),
            patch.object(settings, "secret_key", "testsecretkey"),
        ):

            # Simular múltiplas tentativas inválidas
            ip = "192.168.1.100"
            for _ in range(6):  # Mais que o limite de tentativas
                result, error = await authenticator.verify_credentials(
                    username="wronguser", password="wrongpassword", request_ip=ip
                )

            # Tentar novamente deve resultar em bloqueio
            result, error = await authenticator.verify_credentials(
                username="testadmin", password="testpassword", request_ip=ip
            )

            assert result is False
            assert "Too many failed attempts" in error

    @pytest.mark.asyncio
    async def test_constant_time_comparison(self, authenticator):
        """Teste para garantir comparação em tempo constante."""
        import time

        with (
            patch.object(settings, "admin_username", "testadmin"),
            patch.object(settings, "admin_password", "testpassword"),
            patch.object(settings, "secret_key", "testsecretkey"),
        ):

            # Medir tempo para credenciais válidas
            start_valid = time.time()
            await authenticator.verify_credentials(
                username="testadmin", password="testpassword", request_ip="127.0.0.1"
            )
            time_valid = time.time() - start_valid

            # Medir tempo para credenciais inválidas
            start_invalid = time.time()
            await authenticator.verify_credentials(
                username="wronguser", password="wrongpassword", request_ip="127.0.0.1"
            )
            time_invalid = time.time() - start_invalid

            # Os tempos devem ser próximos (com uma pequena variação aceitável)
            assert abs(time_valid - time_invalid) < 0.05  # 50ms de diferença

    @pytest.mark.asyncio
    async def test_lockout_duration(self, authenticator):
        """Teste da duração do bloqueio de IP."""
        with (
            patch.object(settings, "admin_username", "testadmin"),
            patch.object(settings, "admin_password", "testpassword"),
            patch.object(settings, "secret_key", "testsecretkey"),
        ):

            ip = "192.168.1.200"

            # Bloquear o IP
            for _ in range(6):
                await authenticator.verify_credentials(
                    username="wronguser", password="wrongpassword", request_ip=ip
                )

            # Verificar tempo de bloqueio restante
            result = await authenticator._get_lockout_remaining(ip)

            # O tempo de bloqueio deve ser próximo de 15 minutos
            assert 14 <= result <= 15, f"Lockout time was {result} minutes"

    @pytest.mark.asyncio
    async def test_hmac_hashing(self, authenticator):
        """Teste do método de hash HMAC."""
        # Método privado, então usaremos reflexão
        hash_method = authenticator._hash_credential

        # Testar que hashes de senhas iguais são iguais
        hash1 = hash_method("testpassword")
        hash2 = hash_method("testpassword")

        assert hash1 == hash2, "HMAC hashes for same password should be identical"

        # Testar que hashes de senhas diferentes são diferentes
        hash3 = hash_method("differentpassword")

        assert hash1 != hash3, "HMAC hashes for different passwords should differ"
