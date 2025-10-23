🔴 P0-1: Exceções Granulares em Redis (Simplificado)
Problema
Erros Redis escapam silenciosamente; difícil diagnosticar falhas em desenvolvimento local.​

Solução: Hierarquia de Exceções Customizadas (4h)
Fase 1: Criar Hierarquia de Exceções (1h)
python
# resync/core/exceptions.py
"""Exceções customizadas do Resync."""

class ResyncException(Exception):
    """Exceção base do Resync."""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class RedisInitializationError(ResyncException):
    """Erro ao inicializar Redis."""
    pass


class RedisConnectionError(RedisInitializationError):
    """Erro de conexão ao Redis."""
    pass


class RedisAuthError(RedisInitializationError):
    """Erro de autenticação Redis."""
    pass


class RedisTimeoutError(RedisInitializationError):
    """Timeout em operação Redis."""
    pass


class ConfigurationError(ResyncException):
    """Erro de configuração."""
    pass
Fase 2: Refatorar Redis Initialization (2h)
python
# resync/lifespan.py
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.exceptions import (
    ConnectionError as RedisConnectionErrorBase,
    TimeoutError as RedisTimeoutErrorBase,
    AuthenticationError as RedisAuthErrorBase,
    ResponseError,
    BusyLoadingError,
)

from resync.core.exceptions import (
    RedisConnectionError,
    RedisAuthError,
    RedisTimeoutError,
    RedisInitializationError,
)
from resync.core.structured_logger import logger


@asynccontextmanager
async def redis_connection_manager() -> AsyncIterator:
    """
    Context manager para Redis com cleanup automático.
    
    Yields:
        Redis client validado
        
    Raises:
        RedisConnectionError: Falha de conexão
        RedisAuthError: Falha de autenticação
    """
    from resync.core.async_cache import get_redis_client

    client = None
    try:
        client = await get_redis_client()
        
        # Validar conexão antes de usar
        await client.ping()
        logger.info("redis_connection_validated")
        
        yield client
        
    except RedisConnectionErrorBase as e:
        logger.error(
            "redis_connection_failed",
            error=str(e),
            redis_url=settings.REDIS_URL.split("@")[-1]  # Sem senha no log
        )
        raise RedisConnectionError(
            "Não foi possível conectar ao Redis",
            details={
                "redis_url": settings.REDIS_URL.split("@")[-1],
                "error": str(e),
                "hint": "Verifique se Redis está rodando: redis-cli ping"
            }
        ) from e
        
    except RedisAuthErrorBase as e:
        logger.error("redis_auth_failed", error=str(e))
        raise RedisAuthError(
            "Falha de autenticação no Redis",
            details={
                "error": str(e),
                "hint": "Verifique REDIS_URL no .env"
            }
        ) from e
        
    except RedisTimeoutErrorBase as e:
        logger.error("redis_timeout", error=str(e))
        raise RedisTimeoutError(
            "Timeout ao conectar ao Redis",
            details={
                "error": str(e),
                "hint": "Redis pode estar sobrecarregado ou rede lenta"
            }
        ) from e
        
    finally:
        if client:
            try:
                await client.close()
                await client.connection_pool.disconnect()
                logger.debug("redis_connection_closed")
            except Exception as e:
                logger.warning(
                    "redis_cleanup_warning",
                    error=type(e).__name__,
                    message=str(e)
                )


async def initialize_redis_with_retry(
    max_retries: int = 3,
    base_backoff: float = 0.5,
    max_backoff: float = 5.0
) -> None:
    """
    Inicializa Redis com retry exponencial.
    
    Args:
        max_retries: Máximo de tentativas
        base_backoff: Tempo base de espera (segundos)
        max_backoff: Tempo máximo de espera (segundos)
        
    Raises:
        RedisConnectionError: Redis inacessível após retries
        RedisAuthError: Credenciais inválidas
        RedisTimeoutError: Timeout persistente
    """
    
    # Validar configuração
    if not settings.REDIS_URL:
        logger.critical("redis_url_missing")
        raise ConfigurationError(
            "REDIS_URL não configurado",
            details={"hint": "Adicione REDIS_URL ao arquivo .env"}
        )
    
    logger.info(
        "redis_initialization_started",
        max_retries=max_retries,
        redis_url=settings.REDIS_URL.split("@")[-1]
    )
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            async with redis_connection_manager() as redis_client:
                # Inicializar idempotency manager
                from resync.api.dependencies import initialize_idempotency_manager
                await initialize_idempotency_manager(redis_client)
                
                logger.info(
                    "redis_initialized",
                    attempt=attempt + 1,
                    max_retries=max_retries
                )
                return
                
        except RedisAuthError:
            # Não faz retry em erro de auth
            logger.critical("redis_auth_failed_no_retry")
            raise
            
        except (RedisConnectionError, RedisTimeoutError) as e:
            last_error = e
            
            if attempt >= max_retries - 1:
                # Última tentativa falhou
                logger.critical(
                    "redis_initialization_failed",
                    attempts=max_retries,
                    error=str(e)
                )
                raise
            
            # Calcular backoff exponencial
            backoff = min(max_backoff, base_backoff * (2 ** attempt))
            
            logger.warning(
                "redis_retry_attempt",
                attempt=attempt + 1,
                max_retries=max_retries,
                next_retry_seconds=backoff,
                error=str(e)
            )
            
            await asyncio.sleep(backoff)
            
        except ResponseError as e:
            error_msg = str(e).upper()
            
            # Verificar se é erro de autenticação disfarçado
            if "NOAUTH" in error_msg or "WRONGPASS" in error_msg:
                logger.critical("redis_access_denied", error=str(e))
                raise RedisAuthError(
                    "Redis requer autenticação",
                    details={
                        "error": str(e),
                        "hint": "Adicione senha ao REDIS_URL: redis://:senha@localhost:6379"
                    }
                ) from e
            
            # Outros erros de resposta
            if attempt >= max_retries - 1:
                logger.critical("redis_response_error", error=str(e))
                raise RedisInitializationError(
                    f"Erro Redis: {str(e)}",
                    details={"error": str(e)}
                ) from e
            
            backoff = min(max_backoff, base_backoff * (2 ** attempt))
            await asyncio.sleep(backoff)
            
        except BusyLoadingError as e:
            # Redis ainda carregando
            if attempt >= max_retries - 1:
                logger.critical("redis_busy_loading", error=str(e))
                raise RedisConnectionError(
                    "Redis ocupado carregando dados",
                    details={
                        "error": str(e),
                        "hint": "Aguarde Redis finalizar carga inicial"
                    }
                ) from e
            
            backoff = min(max_backoff, base_backoff * (2 ** attempt))
            logger.warning(
                "redis_busy_retry",
                attempt=attempt + 1,
                backoff_seconds=backoff
            )
            await asyncio.sleep(backoff)
            
        except Exception as e:
            # Erro inesperado - fail fast
            logger.critical(
                "redis_unexpected_error",
                error_type=type(e).__name__,
                error=str(e)
            )
            raise RedisInitializationError(
                f"Erro inesperado ao inicializar Redis: {type(e).__name__}",
                details={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "hint": "Verifique logs para detalhes"
                }
            ) from e
    
    # Se chegou aqui, todas as tentativas falharam
    if last_error:
        raise last_error
Fase 3: Mensagens de Erro Amigáveis (1h)
python
# resync/app_factory.py
from resync.core.exceptions import (
    RedisConnectionError,
    RedisAuthError,
    RedisTimeoutError,
    RedisInitializationError,
    ConfigurationError,
)

class ApplicationFactory:
    """Factory com error handling amigável."""
    
    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        """Lifespan com mensagens de erro claras."""
        
        print("\n🚀 Iniciando Resync HWA Dashboard...")
        
        try:
            # Inicializar Redis
            print("🔌 Conectando ao Redis...")
            await initialize_redis_with_retry()
            print("✅ Redis conectado com sucesso!\n")
            
            # Outras inicializações...
            
            yield
            
        except ConfigurationError as e:
            print(f"\n❌ ERRO DE CONFIGURAÇÃO:")
            print(f"   {e.message}")
            if e.details.get("hint"):
                print(f"   💡 Dica: {e.details['hint']}")
            print()
            sys.exit(2)
            
        except RedisAuthError as e:
            print(f"\n❌ ERRO DE AUTENTICAÇÃO REDIS:")
            print(f"   {e.message}")
            if e.details.get("hint"):
                print(f"   💡 Dica: {e.details['hint']}")
            print(f"\n   Exemplo de .env correto:")
            print(f"   REDIS_URL=redis://:suasenha@localhost:6379")
            print()
            sys.exit(3)
            
        except RedisConnectionError as e:
            print(f"\n❌ ERRO DE CONEXÃO REDIS:")
            print(f"   {e.message}")
            if e.details.get("hint"):
                print(f"   💡 Dica: {e.details['hint']}")
            print(f"\n   Como iniciar Redis localmente:")
            print(f"   1. Instalar: brew install redis (macOS) ou apt install redis (Linux)")
            print(f"   2. Iniciar: redis-server")
            print(f"   3. Testar: redis-cli ping (deve retornar 'PONG')")
            print()
            sys.exit(4)
            
        except RedisTimeoutError as e:
            print(f"\n❌ TIMEOUT REDIS:")
            print(f"   {e.message}")
            if e.details.get("hint"):
                print(f"   💡 Dica: {e.details['hint']}")
            print()
            sys.exit(5)
            
        except RedisInitializationError as e:
            print(f"\n❌ ERRO AO INICIALIZAR REDIS:")
            print(f"   {e.message}")
            if e.details.get("hint"):
                print(f"   💡 Dica: {e.details['hint']}")
            print()
            sys.exit(6)
            
        finally:
            print("\n🛑 Encerrando Resync...")
            await shutdown_services()
            print("✅ Encerrado com sucesso!\n")
🔴 P0-2: Validação Obrigatória de ENV (Simplificado)
Problema
Aplicação inicia com configuração inválida/incompleta.​

Solução: Validação com Pydantic (3h)
Fase 1: Schema de Validação (1.5h)
python
# resync/core/config.py
"""Configuração validada com Pydantic."""

import os
from typing import Optional
from pydantic import (
    BaseSettings,
    Field,
    validator,
    SecretStr,
)


class Settings(BaseSettings):
    """Configurações da aplicação com validação."""
    
    # Ambiente
    environment: str = Field(
        default="development",
        description="Ambiente de execução"
    )
    
    # Autenticação
    admin_username: str = Field(
        ...,  # Obrigatório
        min_length=3,
        description="Username do administrador"
    )
    
    admin_password: SecretStr = Field(
        ...,  # Obrigatório
        min_length=8,
        description="Senha do administrador"
    )
    
    secret_key: SecretStr = Field(
        ...,  # Obrigatório
        min_length=32,
        description="Chave secreta para JWT (mínimo 32 caracteres)"
    )
    
    # Redis
    redis_url: str = Field(
        ...,  # Obrigatório
        description="URL de conexão Redis"
    )
    
    redis_max_connections: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Máximo de conexões no pool Redis"
    )
    
    redis_timeout: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Timeout Redis em segundos"
    )
    
    # TWS
    tws_host: str = Field(
        ...,  # Obrigatório
        min_length=1,
        description="Host do TWS"
    )
    
    tws_port: int = Field(
        ...,  # Obrigatório
        ge=1,
        le=65535,
        description="Porta do TWS"
    )
    
    tws_user: str = Field(
        ...,  # Obrigatório
        min_length=1,
        description="Usuário TWS"
    )
    
    tws_password: SecretStr = Field(
        ...,  # Obrigatório
        min_length=1,
        description="Senha TWS"
    )
    
    # LLM
    llm_endpoint: Optional[str] = Field(
        default=None,
        description="Endpoint do LLM"
    )
    
    llm_api_key: Optional[SecretStr] = Field(
        default=None,
        description="API Key do LLM"
    )
    
    @validator("redis_url")
    def validate_redis_url(cls, v: str) -> str:
        """Valida formato da URL Redis."""
        if not v.startswith("redis://"):
            raise ValueError(
                "REDIS_URL deve começar com 'redis://'. "
                "Exemplo: redis://localhost:6379 ou redis://:senha@localhost:6379"
            )
        return v
    
    @validator("secret_key")
    def validate_secret_key(cls, v: SecretStr) -> SecretStr:
        """Valida que secret_key não é valor padrão óbvio."""
        secret = v.get_secret_value()
        
        forbidden = [
            "changeme",
            "secret",
            "password",
            "0" * 32,
            "a" * 32,
        ]
        
        if any(pattern in secret.lower() for pattern in forbidden):
            raise ValueError(
                "SECRET_KEY não pode ser valor óbvio/padrão. "
                "Gere uma chave aleatória."
            )
        
        return v
    
    @validator("admin_password")
    def validate_password_strength(cls, v: SecretStr) -> SecretStr:
        """Valida força mínima da senha."""
        password = v.get_secret_value()
        
        # Apenas validação básica para ambiente local
        if len(password) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Mensagens de erro customizadas
        @staticmethod
        def _format_error(field: str, error: str) -> str:
            hints = {
                "admin_username": "Defina ADMIN_USERNAME no .env",
                "admin_password": "Defina ADMIN_PASSWORD no .env (mínimo 8 caracteres)",
                "secret_key": "Defina SECRET_KEY no .env (mínimo 32 caracteres aleatórios)",
                "redis_url": "Defina REDIS_URL no .env (exemplo: redis://localhost:6379)",
                "tws_host": "Defina TWS_HOST no .env",
                "tws_port": "Defina TWS_PORT no .env",
                "tws_user": "Defina TWS_USER no .env",
                "tws_password": "Defina TWS_PASSWORD no .env",
            }
            
            hint = hints.get(field, "")
            return f"{error}. {hint}".strip()


def load_settings() -> Settings:
    """
    Carrega e valida configurações.
    
    Returns:
        Settings validadas
        
    Raises:
        ConfigurationError: Configuração inválida
    """
    try:
        settings = Settings()
        return settings
        
    except Exception as e:
        # Formatar erro de forma amigável
        from resync.core.exceptions import ConfigurationError
        
        error_lines = str(e).split("\n")
        message = "Configuração inválida no arquivo .env:"
        
        raise ConfigurationError(
            message,
            details={"errors": error_lines}
        ) from e


# Instância global de settings
try:
    settings = load_settings()
except Exception:
    # Permitir import do módulo mesmo com config inválida
    # Erro será tratado no startup da aplicação
    settings = None
Fase 2: Validação no Startup (1h)
python
# resync/main.py
"""Entry point da aplicação com validação."""

import sys
from resync.core.config import settings, load_settings
from resync.core.exceptions import ConfigurationError


def validate_configuration_on_startup():
    """Valida configuração antes de iniciar aplicação."""
    
    print("\n🔍 Validando configuração...")
    
    try:
        # Forçar reload de settings
        global settings
        settings = load_settings()
        
        print("✅ Configuração válida!")
        print(f"   Ambiente: {settings.environment}")
        print(f"   Redis: {settings.redis_url.split('@')[-1]}")
        print(f"   TWS: {settings.tws_host}:{settings.tws_port}")
        print()
        
        return settings
        
    except ConfigurationError as e:
        print(f"\n❌ ERRO DE CONFIGURAÇÃO:")
        print(f"   {e.message}")
        
        if e.details.get("errors"):
            print("\n   Erros encontrados:")
            for error in e.details["errors"]:
                if error.strip():
                    print(f"   • {error}")
        
        print(f"\n   Crie um arquivo .env na raiz do projeto com:")
        print(f"   ADMIN_USERNAME=admin")
        print(f"   ADMIN_PASSWORD=suasenha123")
        print(f"   SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')")
        print(f"   REDIS_URL=redis://localhost:6379")
        print(f"   TWS_HOST=localhost")
        print(f"   TWS_PORT=31111")
        print(f"   TWS_USER=twsuser")
        print(f"   TWS_PASSWORD=twspass")
        print()
        
        sys.exit(1)


# Validar na importação do módulo
if __name__ != "__main__":
    # Apenas validar quando rodando via uvicorn
    if "uvicorn" in sys.argv[0] or "gunicorn" in sys.argv[0]:
        settings = validate_configuration_on_startup()
Fase 3: Script de Validação Manual (0.5h)
python
# scripts/validate_config.py
#!/usr/bin/env python3
"""Script para validar configuração do .env"""

import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from resync.core.config import load_settings
from resync.core.exceptions import ConfigurationError


def main():
    """Valida configuração e exibe resultado."""
    
    print("\n🔍 Validando configuração Resync...")
    print(f"📁 Diretório: {project_root}")
    
    # Verificar se .env existe
    env_file = project_root / ".env"
    if not env_file.exists():
        print(f"\n❌ Arquivo .env não encontrado em: {env_file}")
        print(f"\n   Crie um arquivo .env com as variáveis necessárias")
        return 1
    
    print(f"✅ Arquivo .env encontrado: {env_file}")
    
    # Validar configuração
    try:
        settings = load_settings()
        
        print("\n✅ CONFIGURAÇÃO VÁLIDA!\n")
        print("📋 Resumo:")
        print(f"   Ambiente: {settings.environment}")
        print(f"   Admin User: {settings.admin_username}")
        print(f"   Redis: {settings.redis_url.split('@')[-1]}")
        print(f"   TWS: {settings.tws_host}:{settings.tws_port}")
        print(f"   TWS User: {settings.tws_user}")
        
        if settings.llm_endpoint:
            print(f"   LLM: {settings.llm_endpoint}")
        
        print()
        return 0
        
    except ConfigurationError as e:
        print(f"\n❌ CONFIGURAÇÃO INVÁLIDA:")
        print(f"   {e.message}\n")
        
        if e.details.get("errors"):
            print("   Erros encontrados:")
            for error in e.details["errors"]:
                if error.strip():
                    print(f"   • {error}")
        
        print(f"\n   💡 Exemplo de .env válido:")
        print(f"   ADMIN_USERNAME=admin")
        print(f"   ADMIN_PASSWORD=MinhaS3nh@Forte")
        print(f"   SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')")
        print(f"   REDIS_URL=redis://localhost:6379")
        print(f"   TWS_HOST=localhost")
        print(f"   TWS_PORT=31111")
        print(f"   TWS_USER=twsuser")
        print(f"   TWS_PASSWORD=twspass")
        print()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())