"""Field validators for the Settings class.

This module contains all Pydantic field validators used by the Settings class
to keep the main settings module more focused and maintainable.
"""

import warnings
from pathlib import Path

from pydantic import SecretStr, ValidationInfo, field_validator

from .settings_types import Environment


class SettingsValidators:
    """Collection of field validators for Settings class."""

    @field_validator("base_dir")
    @classmethod
    def validate_base_dir(cls, v: Path) -> Path:
        """Resolve base_dir para path absoluto e valida existência."""
        resolved_path = v.resolve()
        if not resolved_path.exists():
            raise ValueError(f"base_dir ({resolved_path}) does not exist")
        if not resolved_path.is_dir():
            raise ValueError(f"base_dir ({resolved_path}) is not a directory")
        return resolved_path

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_db_pool_sizes(cls, v: int, info: ValidationInfo) -> int:
        """Valida que max_size >= min_size."""
        min_size = info.data.get("db_pool_min_size", 0)
        if v < min_size:
            raise ValueError(
                f"db_pool_max_size ({v}) must be >= db_pool_min_size ({min_size})"
            )
        return v

    @field_validator("redis_pool_max_size")
    @classmethod
    def validate_redis_pool_sizes(cls, v: int, info: ValidationInfo) -> int:
        """Valida que max_size >= min_size e aplica fallback de legado."""
        min_size = info.data.get("redis_pool_min_size", 0)
        if v < min_size:
            raise ValueError(
                "redis_pool_max_size ({v}) must be >= "
                f"redis_pool_min_size ({min_size})"
            )

        # Aplicar fallback de legado com warning
        legacy_min_size = info.data.get("redis_min_connections")
        legacy_max_size = info.data.get("redis_max_connections")

        if legacy_min_size is not None and legacy_max_size is not None:
            # Se os defaults ainda estão ativos, permite fallback de compat.
            if info.data.get("redis_pool_min_size") == 5 and v == 20:
                warnings.warn(
                    "redis_min/max_connections are deprecated. "
                    "Use redis_pool_min/max_size instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                min_size = legacy_min_size
                v = legacy_max_size
                if v < min_size:
                    raise ValueError(
                        "redis_pool_max_size ({v}) must be >= "
                        f"redis_pool_min_size ({min_size})"
                    )
        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Valida formato da URL Redis."""
        if not (v.startswith(("redis://", "rediss://"))):
            raise ValueError(
                "REDIS_URL deve começar com 'redis://' ou 'rediss://'. "
                "Exemplo: redis://localhost:6379 ou rediss://localhost:6379"
            )
        return v

    @field_validator("admin_password")
    @classmethod
    def validate_password_strength(
        cls, v: SecretStr | None, info: ValidationInfo
    ) -> SecretStr | None:
        """Valida força mínima da senha."""
        env = info.data.get("environment")

        # Em produção: senha obrigatória com 8+ caracteres
        if env == Environment.PRODUCTION:
            if v is None or len(v.get_secret_value()) < 8:
                raise ValueError(
                    "Senha do admin deve ter no mínimo 8 caracteres (produção)"
                )
        # Em desenvolvimento: permitir None, mas se definida, exigir 8+ caracteres
        else:
            if v is not None and len(v.get_secret_value()) < 8:
                raise ValueError("Senha deve ter no mínimo 8 caracteres")
        return v

    @field_validator("admin_password")
    @classmethod
    def validate_insecure_in_prod(
        cls, v: SecretStr | None, info: ValidationInfo
    ) -> SecretStr | None:
        """Bloqueia senhas inseguras em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION and v is not None:
            insecure = {
                "change_me_please",
                "change_me_immediately",
                "admin",
                "password",
                "12345678",
            }
            if v.get_secret_value().lower() in insecure:
                raise ValueError(
                    "Insecure admin password not allowed in production"
                )
        return v

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_production_cors(
        cls, v: list[str], info: ValidationInfo
    ) -> list[str]:
        """Valida CORS em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION and "*" in v:
            raise ValueError("Wildcard CORS origins not allowed in production")
        return v

    @field_validator("cors_allow_credentials")
    @classmethod
    def validate_credentials_with_wildcard(
        cls, v: bool, info: ValidationInfo
    ) -> bool:
        """Valida credenciais com wildcard origins."""
        origins = info.data.get("cors_allowed_origins", [])
        if v and "*" in origins:
            warnings.warn(
                "CORS wildcard origins with credentials allowed is insecure. "
                "Consider using explicit origins instead of wildcard.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(
        cls, v: SecretStr, info: ValidationInfo
    ) -> SecretStr:
        """Valida chave da API em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION:
            if not v.get_secret_value() or v.get_secret_value() == (
                "dummy_key_for_development"
            ):
                raise ValueError(
                    "LLM_API_KEY must be set to a valid key in production"
                )
        return v

    @field_validator("neo4j_password")
    @classmethod
    def validate_neo4j_password_production(
        cls, v: SecretStr, info: ValidationInfo
    ) -> SecretStr:
        """Valida senha Neo4j em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION and not v.get_secret_value():
            raise ValueError("NEO4J_PASSWORD must be set in production")
        return v

    @field_validator("tws_verify")
    @classmethod
    def validate_tws_verify_warning(
        cls, v: bool | str, info: ValidationInfo
    ) -> bool | str:
        """Emite warning para TWS verification em produção."""
        env = info.data.get("environment")
        is_disabled = (v is False) or (
            isinstance(v, str) and v.lower() == "false"
        )
        if env == Environment.PRODUCTION and is_disabled:
            warnings.warn(
                "TWS verification is disabled in production. This is a security risk.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("neo4j_uri")
    @classmethod
    def validate_neo4j_uri_warning(cls, v: str, info: ValidationInfo) -> str:
        """Emite warning para Neo4j URI sem TLS em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION and v.startswith("neo4j://"):
            warnings.warn(
                "Neo4j URI uses unencrypted connection (neo4j://). Consider using "
                "neo4j+s:// for production.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("tws_user", "tws_password")
    @classmethod
    def validate_tws_credentials(
        cls, v: str | None, info: ValidationInfo
    ) -> str | None:
        """Valida credenciais TWS quando não está em mock mode."""
        if info.field_name == "tws_password" and v:
            env = info.data.get("environment")
            mock_mode = info.data.get("tws_mock_mode")
            if env == Environment.PRODUCTION and not mock_mode:
                # SecretStr esperado; valida conteúdo
                if not v.get_secret_value():
                    raise ValueError(
                        "TWS_PASSWORD is required when not in mock mode"
                    )
                if len(v.get_secret_value()) < 12:
                    raise ValueError(
                        "TWS_PASSWORD must be at least 12 characters in production"
                    )
                common_passwords = {
                    "password",
                    "twsuser",
                    "tws_password",
                    "change_me",
                }
                if v.get_secret_value().lower() in common_passwords:
                    raise ValueError(
                        "TWS_PASSWORD cannot be a common/default password"
                    )
        return v




