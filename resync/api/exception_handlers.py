"""Exception handlers globais para FastAPI.

Este módulo implementa handlers para todas as exceções da aplicação,
convertendo-as em respostas HTTP padronizadas seguindo RFC 7807.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from resync.core.context import get_correlation_id
from resync.core.exceptions_enhanced import ResyncException
from resync.utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BaseAppException,
    InternalError,
    RateLimitError,
    ResourceConflictError,
    ResourceNotFoundError,
    ValidationError,
)
from resync.utils.simple_logger import get_logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from resync.api.models.responses import (
    ValidationErrorDetail,
    create_problem_detail,
    create_validation_problem_detail,
)

logger = get_logger(__name__)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================


async def base_app_exception_handler(
    request: Request, exc: BaseAppException
) -> JSONResponse:
    """Handler para exceções da aplicação (BaseAppException).

    Args:
        request: Requisição HTTP
        exc: Exceção da aplicação

    Returns:
        JSONResponse com problema detalhado
    """
    # Logar exceção
    logger.error(
        f"Application exception: {exc.message}",
        error_code=exc.error_code.value,
        status_code=exc.status_code,
        correlation_id=exc.correlation_id,
        path=request.url.path,
        method=request.method,
        exc_info=exc.original_exception is not None,
    )

    # Criar problem detail
    problem = create_problem_detail(
        type_uri=f"https://api.example.com/errors/{exc.error_code.value.lower()}",
        title=exc.error_code.name.replace("_", " ").title(),
        status=exc.status_code,
        detail=exc.message,
        instance=str(request.url.path),
    )

    # Adicionar headers específicos
    headers = {}

    # Rate limiting
    if isinstance(exc, RateLimitError) and exc.details.get("retry_after"):
        headers["Retry-After"] = str(exc.details["retry_after"])

    # Correlation ID
    if exc.correlation_id:
        headers["X-Correlation-ID"] = exc.correlation_id

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
    )


async def resync_exception_handler(
    request: Request, exc: ResyncException
) -> JSONResponse:
    """Handler para exceções ResyncException.

    Args:
        request: Requisição HTTP
        exc: Exceção ResyncException

    Returns:
        JSONResponse com problema detalhado
    """
    correlation_id = get_correlation_id()

    # Logar exceção
    logger.error(
        f"Resync exception: {exc.message}",
        error_code=exc.error_code,
        severity=exc.severity,
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
        exc_info=exc.original_exception is not None,
    )

    # Mapear severity para status code
    status_mapping = {
        "low": 400,
        "LOW": 400,
        "medium": 404,
        "MEDIUM": 404,
        "high": 422,
        "HIGH": 422,
        "critical": 500,
        "CRITICAL": 500,
    }
    status_code = status_mapping.get(exc.severity, 500)

    # Criar problem detail
    problem = create_problem_detail(
        type_uri=f"https://api.example.com/errors/{exc.error_code.lower()}",
        title=exc.error_code.replace("_", " ").title(),
        status=status_code,
        detail=exc.user_friendly_message or exc.message,
        instance=str(request.url.path),
    )

    headers = {}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError | PydanticValidationError
) -> JSONResponse:
    """Handler para erros de validação do Pydantic/FastAPI.

    Args:
        request: Requisição HTTP
        exc: Exceção de validação

    Returns:
        JSONResponse com erros de validação detalhados
    """
    correlation_id = get_correlation_id()

    # Logar erro
    logger.warning(
        "Validation error",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
        errors=exc.errors(),
    )

    # Converter erros do Pydantic para nosso formato
    validation_errors = []

    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])

        validation_errors.append(
            ValidationErrorDetail(
                field=field,
                message=error["msg"],
                code=error["type"],
                value=error.get("input"),
            )
        )

    # Criar problem detail
    problem = create_validation_problem_detail(
        errors=validation_errors,
        detail=f"Validation failed with {len(validation_errors)} error(s)",
        instance=str(request.url.path),
    )

    headers = {}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handler para exceções HTTP do Starlette.

    Args:
        request: Requisição HTTP
        exc: Exceção HTTP

    Returns:
        JSONResponse com problema detalhado
    """
    correlation_id = get_correlation_id()

    # Logar exceção
    logger.warning(
        f"HTTP exception: {exc.detail}",
        status_code=exc.status_code,
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
    )

    # Mapear para nossa exceção
    if exc.status_code == 404:
        ResourceNotFoundError(
            message=str(exc.detail), correlation_id=correlation_id
        )
    elif exc.status_code == 401:
        AuthenticationError(
            message=str(exc.detail), correlation_id=correlation_id
        )
    elif exc.status_code == 403:
        AuthorizationError(
            message=str(exc.detail), correlation_id=correlation_id
        )
    elif exc.status_code == 409:
        ResourceConflictError(
            message=str(exc.detail), correlation_id=correlation_id
        )
    elif exc.status_code == 429:
        RateLimitError(message=str(exc.detail), correlation_id=correlation_id)
    elif exc.status_code >= 500:
        InternalError(message=str(exc.detail), correlation_id=correlation_id)
    else:
        ValidationError(message=str(exc.detail), correlation_id=correlation_id)

    # Criar problem detail
    problem = create_problem_detail(
        type_uri=f"https://httpstatuses.com/{exc.status_code}",
        title="HTTP Exception",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=str(request.url.path),
    )

    headers = {}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handler para exceções não tratadas.

    Args:
        request: Requisição HTTP
        exc: Exceção não tratada

    Returns:
        JSONResponse com erro interno
    """
    correlation_id = get_correlation_id()

    # Logar exceção com stack trace
    logger.critical(
        f"Unhandled exception: {str(exc)}",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
        exc_info=True,
    )

    # Criar exceção interna
    InternalError(
        message="An unexpected error occurred",
        details={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
        correlation_id=correlation_id,
        original_exception=exc,
    )

    # Criar problem detail - CORRIGIDO: Não usar exc.status_code ou exc.detail pois Exception não tem esses atributos
    problem = create_problem_detail(
        type_uri="https://httpstatuses.com/500",
        title="Internal Server Error",
        status=500,
        detail="An unexpected error occurred",
        instance=str(request.url.path),
    )

    headers = {}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
    )


# ============================================================================
# REGISTRATION HELPER
# ============================================================================


def register_exception_handlers(app) -> None:
    """Registra todos os exception handlers na aplicação FastAPI.

    Args:
        app: Instância da aplicação FastAPI
    """
    # Exceções da aplicação (BaseAppException)
    app.add_exception_handler(BaseAppException, base_app_exception_handler)

    # Exceções ResyncException (enhanced exceptions)
    app.add_exception_handler(ResyncException, resync_exception_handler)

    # Exceções de validação
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(
        PydanticValidationError, validation_exception_handler
    )

    # Exceções HTTP do Starlette
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Exceções não tratadas
    app.add_exception_handler(Exception, unhandled_exception_handler)

    logger.info("Exception handlers registered successfully")


__all__ = [
    "base_app_exception_handler",
    "resync_exception_handler",
    "validation_exception_handler",
    "http_exception_handler",
    "unhandled_exception_handler",
    "register_exception_handlers",
]




