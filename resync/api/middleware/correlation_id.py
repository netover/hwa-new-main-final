"""Middleware para gerenciamento de Correlation IDs.

Este middleware implementa o padrão de Correlation ID para rastreamento
distribuído de requisições através de múltiplos serviços e componentes.

O Correlation ID é:
- Gerado automaticamente se não fornecido
- Propagado através de headers HTTP
- Disponível em todo o contexto da requisição
- Incluído em logs e respostas de erro
"""

import logging
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Nome do header para Correlation ID
CORRELATION_ID_HEADER = "X-Correlation-ID"
CORRELATION_ID_CTX_KEY = "correlation_id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware para gerenciar Correlation IDs em requisições HTTP.

    Funcionalidades:
    - Extrai Correlation ID do header da requisição
    - Gera novo ID se não fornecido
    - Armazena no contexto da requisição
    - Adiciona ao header da resposta
    - Disponibiliza para logging

    Attributes:
        header_name: Nome do header HTTP para o Correlation ID
        generate_if_missing: Se True, gera ID quando não fornecido
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = CORRELATION_ID_HEADER,
        generate_if_missing: bool = True,
    ):
        """Inicializa o middleware.

        Args:
            app: Aplicação ASGI
            header_name: Nome do header para Correlation ID
            generate_if_missing: Se deve gerar ID quando ausente
        """
        super().__init__(app)
        self.header_name = header_name
        self.generate_if_missing = generate_if_missing

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa a requisição adicionando Correlation ID.

        Args:
            request: Requisição HTTP
            call_next: Próximo handler na cadeia

        Returns:
            Resposta HTTP com Correlation ID no header
        """
        # Extrair ou gerar Correlation ID
        correlation_id = request.headers.get(self.header_name)

        if not correlation_id and self.generate_if_missing:
            correlation_id = self._generate_correlation_id()
            logger.debug(
                f"Generated new correlation ID: {correlation_id}",
                extra={"correlation_id": correlation_id},
            )
        elif correlation_id:
            logger.debug(
                f"Using existing correlation ID: {correlation_id}",
                extra={"correlation_id": correlation_id},
            )

        # Armazenar no contexto da requisição
        if correlation_id:
            request.state.correlation_id = correlation_id

            # Também disponibilizar via contextvars para acesso global
            from resync.core.context import set_correlation_id

            set_correlation_id(correlation_id)

        # Processar requisição
        try:
            response = await call_next(request)
        except Exception as e:
            # Garantir que correlation_id está disponível mesmo em caso de erro
            logger.error(
                f"Error processing request: {str(e)}",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            raise

        # Adicionar Correlation ID ao header da resposta
        if correlation_id:
            response.headers[self.header_name] = correlation_id

        return response

    def _generate_correlation_id(self) -> str:
        """Gera um novo Correlation ID único.

        Returns:
            UUID v4 como string
        """
        return str(uuid.uuid4())


def get_correlation_id_from_request(request: Request) -> Optional[str]:
    """Extrai Correlation ID da requisição.

    Args:
        request: Requisição HTTP

    Returns:
        Correlation ID se disponível, None caso contrário
    """
    return getattr(request.state, CORRELATION_ID_CTX_KEY, None)


def add_correlation_id_to_response(
    response: Response, correlation_id: str, header_name: str = CORRELATION_ID_HEADER
) -> None:
    """Adiciona Correlation ID ao header da resposta.

    Args:
        response: Resposta HTTP
        correlation_id: ID de correlação
        header_name: Nome do header
    """
    response.headers[header_name] = correlation_id


__all__ = [
    "CorrelationIdMiddleware",
    "CORRELATION_ID_HEADER",
    "CORRELATION_ID_CTX_KEY",
    "get_correlation_id_from_request",
    "add_correlation_id_to_response",
]
