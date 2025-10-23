import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from resync.core.fastapi_di import get_tws_client
from resync.core.interfaces import ITWSClient
from resync.core.rate_limiter import authenticated_rate_limit
from resync.settings import settings

logger = logging.getLogger(__name__)

cache_router = APIRouter()

# Define o esquema de segurança: espera credenciais Basic Auth.
security = HTTPBasic()

# Module-level dependencies to avoid B008 errors
security_dependency = Depends(security)
tws_client_dependency = Depends(get_tws_client)


async def verify_admin_credentials(
    creds: HTTPBasicCredentials = security_dependency,
) -> HTTPBasicCredentials:
    """
    Dependência para verificar as credenciais de administrador usando Basic Auth.

    Esta função é usada como uma dependência de segurança para endpoints
    administrativos. Ela valida o nome de usuário e a senha fornecidos
    contra as credenciais definidas no sistema.

    Utiliza `secrets.compare_digest` para uma comparação segura que previne
    ataques de timing.

    Args:
        creds: Credenciais HTTPBasic injetadas pelo FastAPI.

    Raises:
        HTTPException: Lança um erro 401 Unauthorized se as credenciais
                       forem inválidas.
    """
    # Busca as credenciais de administrador a partir das configurações da aplicação.
    admin_user: Optional[str] = settings.ADMIN_USERNAME
    admin_pass: Optional[str] = settings.ADMIN_PASSWORD

    # Garante que as credenciais de administrador estão configuradas no servidor.
    if not admin_user or not admin_pass:
        logger.error("Admin credentials not configured on the server")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="As credenciais de administrador não estão configuradas no servidor.",
        )

    correct_username = secrets.compare_digest(creds.username, admin_user)
    correct_password = secrets.compare_digest(creds.password, admin_pass)

    if not (correct_username and correct_password):
        logger.warning(
            f"Failed admin authentication attempt for user: {creds.username}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de administrador inválidas ou ausentes.",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info(f"Successful admin authentication for user: {creds.username}")
    return creds


@cache_router.post(
    "/invalidate",
    summary="Invalidate TWS Cache",
)
@authenticated_rate_limit
async def invalidate_tws_cache(
    scope: str = "system",  # 'system', 'jobs', 'workstations'
    tws_client: ITWSClient = tws_client_dependency,
    # Call verify_admin_credentials inside the function to handle rate limiting properly
    creds: HTTPBasicCredentials = security_dependency,
) -> dict[str, str]:
    """
    Invalidates the TWS data cache based on the specified scope.
    Requires administrator credentials via HTTP Basic Auth for authorization.

    - **scope='system'**: Invalidates all TWS-related caches.
    - **scope='jobs'**: Invalidates only the main job list cache.
    - **scope='workstations'**: Invalidates only the workstation list cache.
    """
    # Verify admin credentials inside the function to handle rate limiting properly
    await verify_admin_credentials(creds)

    # Log the cache invalidation request for security auditing
    logger.info(
        f"Cache invalidation requested by user '{creds.username}' with scope '{scope}'"
    )

    if scope == "system":
        await tws_client.invalidate_system_cache()
        logger.info("Full TWS system cache invalidated successfully")
        return {"status": "success", "detail": "Full TWS system cache invalidated."}
    elif scope == "jobs":
        await tws_client.invalidate_all_jobs()
        logger.info("All jobs list cache invalidated successfully")
        return {"status": "success", "detail": "All jobs list cache invalidated."}
    elif scope == "workstations":
        await tws_client.invalidate_all_workstations()
        logger.info("All workstations list cache invalidated successfully")
        return {
            "status": "success",
            "detail": "All workstations list cache invalidated.",
        }
    else:
        logger.warning(f"Invalid scope '{scope}' provided for cache invalidation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope '{scope}'. Must be 'system', 'jobs', or 'workstations'.",
        )
