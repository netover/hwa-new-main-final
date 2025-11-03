from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.trace import TracerProvider

from resync.core.distributed_tracing import setup_tracing, traced


class TestDistributedTracing:
    """Testes para o DistributedTracing."""

    @pytest.fixture
    def tracer_provider(self):
        """Fixture para criar um provedor de tracer."""
        return TracerProvider()

    @pytest.mark.asyncio
    async def test_setup_tracing(self, monkeypatch):
        """Testar configuração do tracing."""
        # Mockar o exporter
        mock_exporter = MagicMock()

        # Mockar o tracer provider
        mock_tracer = MagicMock()
        mock_tracer.create_span = MagicMock(return_value=MagicMock())

        with patch(
            "resync.core.distributed_tracing.OTLPSpanExporter",
            lambda *args, **kwargs: mock_exporter,
        ), patch(
            "resync.core.distributed_tracing.TracerProvider", lambda: mock_tracer
        ):
            setup_tracing(app=MagicMock())

            # Verificar que o tracer foi configurado corretamente
            assert mock_exporter.create_span.called

    @pytest.mark.asyncio
    async def test_traced_decorator(self):
        """Testar o decorator traced."""

        # Função de exemplo
        @traced(name="test_function", attributes={"test": "true"})
        async def example_function():
            return "result"

        # Mockar o tracer
        mock_tracer = MagicMock()

        with patch(
            "resync.core.distributed_tracing.trace.get_tracer_provider",
            lambda: mock_tracer,
        ):
            result = await example_function()

            # Verificar que o span foi criado
            mock_tracer.start_as_current_span.assert_called()

            # Verificar que a função foi executada corretamente
            assert result == "result"




