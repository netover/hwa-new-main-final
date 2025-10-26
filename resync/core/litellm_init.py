"""
LiteLLM initialization for Resync TWS application.

This module sets up LiteLLM with proper configuration for
TWS-specific use cases, including local Ollama and remote API models.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional, Protocol, runtime_checkable

from resync.settings import settings

logger = logging.getLogger(__name__)


class LiteLLMMetrics:
    """Classe para gerenciar métricas operacionais do LiteLLM de forma thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.init_success: int = 0
        self.init_fail_reason: dict[str, int] = {}
        self.cost_calc_fail: int = 0

    def increment_init_success(self) -> None:
        """Incrementa contador de inicializações bem-sucedidas."""
        with self._lock:
            self.init_success += 1

    def increment_init_fail_reason(self, reason: str) -> None:
        """Incrementa contador de falhas de inicialização por motivo."""
        with self._lock:
            self.init_fail_reason[reason] = self.init_fail_reason.get(reason, 0) + 1

    def increment_cost_calc_fail(self) -> None:
        """Incrementa contador de falhas de cálculo de custo."""
        with self._lock:
            self.cost_calc_fail += 1

    def get_metrics(self) -> dict[str, Any]:
        """Retorna cópia thread-safe das métricas."""
        with self._lock:
            return {
                "init_success": self.init_success,
                "init_fail_reason": self.init_fail_reason.copy(),
                "cost_calc_fail": self.cost_calc_fail,
            }


class LiteLLMManager:
    """Gerenciador thread-safe do LiteLLM Router."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._router: Optional[RouterLike] = None
        self._metrics = LiteLLMMetrics()

    def get_router(self) -> Optional[RouterLike]:
        """Retorna instância singleton (thread-safe)."""
        with self._lock:
            if self._router is None:
                self._router = self._initialize_litellm()
            return self._router

    def reset_router(self) -> None:
        """Reseta o singleton (útil para testes)."""
        with self._lock:
            self._router = None

    def _initialize_litellm(self) -> Optional[RouterLike]:
        """Inicializa LiteLLM Router com base em settings."""
        strict = bool(getattr(settings, "LITELLM_STRICT_INIT", False))
        try:
            from litellm import Router as LiteLLMRouter  # type: ignore

            _apply_env_from_settings()

            enable_checks = getattr(settings, "LITELLM_PRE_CALL_CHECKS", True)
            kwargs: dict[str, Any] = {"enable_pre_call_checks": enable_checks}

            model_list = getattr(settings, "LITELLM_MODEL_LIST", None)
            if model_list is not None:
                kwargs["model_list"] = model_list  # apenas se houver

            # Parâmetros adicionais opcionais (quando existirem em settings)
            for k_setting, k_arg in [
                ("LITELLM_NUM_RETRIES", "num_retries"),
                ("LITELLM_TIMEOUT", "timeout"),
            ]:
                val = getattr(settings, k_setting, None)
                if val is not None:
                    kwargs[k_arg] = val

            router: RouterLike = LiteLLMRouter(**kwargs)  # type: ignore[call-arg]
            logger.info(
                "LiteLLM initialized (pre_checks=%s, model_list=%s)",
                enable_checks,
                "provided" if model_list is not None else "default",
            )

            # Atualiza métricas
            self._metrics.increment_init_success()

            return router

        except ImportError as import_err:
            logger.warning("LiteLLM not installed: %s", import_err, exc_info=False)
            self._metrics.increment_init_fail_reason("ImportError")
            if strict:
                raise
            return None
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as err:
            logger.exception("Failed to initialize LiteLLM")
            err_type = type(err).__name__
            self._metrics.increment_init_fail_reason(err_type)
            if strict:
                raise
            return None
        except (OSError, ConnectionError, TimeoutError) as err:
            # Guarda-chuva defensivo para ambientes heterogêneos
            logger.exception("Unexpected error initializing LiteLLM")
            err_type = type(err).__name__
            self._metrics.increment_init_fail_reason(err_type)
            if strict:
                raise
            return None

    def get_metrics(self) -> dict[str, Any]:
        """Retorna métricas operacionais do LiteLLM."""
        metrics = self._metrics.get_metrics()
        metrics["router_initialized"] = self._router is not None
        return metrics

    def calculate_completion_cost(self, completion_response: Any) -> float:
        """
        Calcula o custo da resposta usando LiteLLM. Retorna 0.0 se indisponível/erro.
        """
        try:
            from litellm import completion_cost  # type: ignore
        except ImportError as import_err:
            logger.info(
                "Cost calculation unavailable (litellm not installed?): %s",
                import_err,
                exc_info=False,
            )
            return 0.0

        try:
            return float(completion_cost(completion_response=completion_response))
        except (ValueError, TypeError, KeyError) as err:
            logger.warning("Could not calculate completion cost: %s", err, exc_info=False)
            self._metrics.increment_cost_calc_fail()
            return 0.0


# Singleton manager instance
_LITELLM_MANAGER = LiteLLMManager()


@runtime_checkable
class RouterLike(Protocol):
    """Protocolo mínimo para o Router LiteLLM."""

    def completion(self, *args, **kwargs):  # type: ignore
        """Método de completion do router LiteLLM."""


def _set_env(name: str, value: Optional[str], *, overwrite: bool = False) -> bool:
    """
    Define uma variável de ambiente se houver valor. Por padrão, não sobrescreve.
    Retorna True se a variável foi definida/alterada.
    """
    if value is None:
        return False
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return False
    if overwrite or name not in os.environ:
        os.environ[name] = value  # type: ignore[arg-type]
        return True
    return False


def _apply_env_from_settings(*, overwrite: bool = False) -> dict[str, bool]:
    """
    Popula env vars a partir de settings. Não sobrescreve por padrão.
    Retorna um mapa {VAR: mudou?} para facilitar testes/observabilidade.
    """
    changed: dict[str, bool] = {}

    endpoint = getattr(settings, "LLM_ENDPOINT", None)
    # Fonte de verdade: OPENAI_BASE_URL; só preenche OPENAI_API_BASE se não existir
    changed["OPENAI_BASE_URL"] = _set_env("OPENAI_BASE_URL", endpoint, overwrite=overwrite)
    changed["OPENAI_API_BASE"] = _set_env(
        "OPENAI_API_BASE",
        endpoint if ("OPENAI_API_BASE" not in os.environ or overwrite) else None,
        overwrite=overwrite,
    )

    llm_key = getattr(settings, "LLM_API_KEY", None)
    changed["OPENAI_API_KEY"] = _set_env("OPENAI_API_KEY", llm_key, overwrite=overwrite)

    or_key = getattr(settings, "OPENROUTER_API_KEY", None)
    changed["OPENROUTER_API_KEY"] = _set_env("OPENROUTER_API_KEY", or_key, overwrite=overwrite)

    or_base = getattr(settings, "OPENROUTER_API_BASE", None)
    changed["OPENROUTER_API_BASE"] = _set_env("OPENROUTER_API_BASE", or_base, overwrite=overwrite)

    # Loga quais variáveis foram definidas (nunca os valores)
    set_vars = [k for k, v in changed.items() if v]
    if set_vars:
        logger.debug("LLM env set: %s", ", ".join(set_vars))
    return changed


# Funções de compatibilidade mantendo a API pública original
def get_litellm_router() -> Optional[RouterLike]:
    """
    Retorna instância singleton (thread-safe).
    """
    return _LITELLM_MANAGER.get_router()


def reset_litellm_router() -> None:
    """
    Reseta o singleton (útil para testes).
    """
    _LITELLM_MANAGER.reset_router()


def initialize_litellm(*, overwrite_env: bool = False) -> Optional[RouterLike]:
    """
    Inicializa LiteLLM Router com base em settings.
    overwrite_env: se True, sobrescreve variáveis de ambiente existentes.
    Pode lançar em modo estrito via settings.LITELLM_STRICT_INIT.
    """
    # Forçar reinicialização quando overwrite_env for True
    if overwrite_env:
        _LITELLM_MANAGER.reset_router()

    return _LITELLM_MANAGER.get_router()


def calculate_completion_cost(completion_response: Any) -> float:
    """
    Calcula o custo da resposta usando LiteLLM. Retorna 0.0 se indisponível/erro.
    """
    return _LITELLM_MANAGER.calculate_completion_cost(completion_response)


def get_litellm_metrics() -> dict[str, Any]:
    """
    Retorna métricas operacionais do LiteLLM.
    """
    return _LITELLM_MANAGER.get_metrics()
