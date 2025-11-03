# __init__.py — Public API (lazy, robust, backwards-friendly)

from __future__ import annotations

import os
import warnings
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING, Any

# ---------------------------------------------------------------------------
# Package metadata (dinâmico quando possível, com fallback estável)
# ---------------------------------------------------------------------------
try:
    # Resolve pelo nome do pacote raiz (mais resiliente em workspaces)
    __version__ = _pkg_version(__name__.split(".", 1)[0])
except PackageNotFoundError:
    # Fallback para nome comum do pacote/distribution (ajuste se necessário)
    try:
        __version__ = _pkg_version("health_service_components")
    except PackageNotFoundError:
        __version__ = "0.0.0"

__doc__ = (
    "Health Service Components — Public API facade with lazy-loading.\n\n"
    "Design goals:\n"
    "- Lazy import (PEP 562) to minimize startup time and avoid import cycles.\n"
    "- Single source of truth for public exports (no drift with __all__).\n"
    "- Backward compatibility via per-symbol DeprecationWarning.\n"
    "- Optional fast-path: preload essentials or strict import validation.\n\n"
    "Environment flags:\n"
    "- HSC_PRELOAD_ESSENTIALS=1   -> Preloads selected hot-path symbols.\n"
    "- HSC_STRICT_IMPORTS=1       -> Imports and validates all exports at "
    "import time.\n"
)

# ---------------------------------------------------------------------------
# Public export map: Symbol -> (submodule, attribute)
# Mantém a API pública coesa e evita divergência entre imports e __all__.
# ---------------------------------------------------------------------------
_EXPORTS: dict[str, tuple[str, str]] = {
    # Core orchestration
    "HealthServiceOrchestrator": (
        "health_service_orchestrator",
        "HealthServiceOrchestrator",
    ),
    "HealthServiceManager": ("health_service_manager", "HealthServiceManager"),
    # Monitoring components
    "ProactiveHealthMonitor": ("proactive_monitor", "ProactiveHealthMonitor"),
    "PerformanceMetricsCollector": (
        "performance_metrics_collector",
        "PerformanceMetricsCollector",
    ),
    "HealthMonitoringCoordinator": (
        "health_monitoring_coordinator",
        "HealthMonitoringCoordinator",
    ),
    "HealthMonitoringAggregator": (
        "monitoring_aggregator",
        "HealthMonitoringAggregator",
    ),
    # Circuit breaker functionality
    "CircuitBreaker": ("circuit_breaker", "CircuitBreaker"),
    "CircuitBreakerManager": (
        "circuit_breaker_manager",
        "CircuitBreakerManager",
    ),
    # Caching and history
    "ComponentCacheManager": (
        "component_cache_manager",
        "ComponentCacheManager",
    ),
    "HealthHistoryManager": ("health_history_manager", "HealthHistoryManager"),
    # Memory management
    "MemoryManager": ("memory_manager", "MemoryManager"),
    "MemoryUsageTracker": ("memory_usage_tracker", "MemoryUsageTracker"),
    # Recovery and alerting
    "HealthRecoveryManager": ("recovery_manager", "HealthRecoveryManager"),
    "HealthAlerting": ("health_alerting", "HealthAlerting"),
    # Configuration & utilities
    "HealthCheckConfigurationManager": (
        "health_config_manager",
        "HealthCheckConfigurationManager",
    ),
    "HealthCheckUtils": ("health_check_utils", "HealthCheckUtils"),
    "HealthCheckRetry": ("health_check_retry", "HealthCheckRetry"),
    # Global service management
    "GlobalHealthServiceManager": (
        "global_health_service_manager",
        "GlobalHealthServiceManager",
    ),
    "get_global_health_service": (
        "global_health_service_manager",
        "get_global_health_service",
    ),
    "shutdown_global_health_service": (
        "global_health_service_manager",
        "shutdown_global_health_service",
    ),
    "get_current_global_health_service": (
        "global_health_service_manager",
        "get_current_global_health_service",
    ),
    "is_global_health_service_initialized": (
        "global_health_service_manager",
        "is_global_health_service_initialized",
    ),
    # Legacy support (mantido com aviso de deprecação)
    "HealthCheckService": ("health_check_service", "HealthCheckService"),
}

__all__ = tuple(_EXPORTS.keys())

# ---------------------------------------------------------------------------
# Deprecations — mensagens específicas por símbolo legado
# ---------------------------------------------------------------------------
_DEPRECATED: dict[str, str] = {
    "HealthCheckService": (
        "HealthCheckService é legado e será removido em versão futura; "
        "prefira HealthServiceManager ou HealthServiceOrchestrator conforme o caso."
    ),
}

# ---------------------------------------------------------------------------
# Helpers de ambiente (pré-carregamento opcional de essenciais)
# ---------------------------------------------------------------------------
_ESSENTIALS = (
    "get_global_health_service",
    "shutdown_global_health_service",
    "is_global_health_service_initialized",
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Lazy loader (PEP 562) com memoization e deprecação por símbolo
# ---------------------------------------------------------------------------
def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc

    if name in _DEPRECATED:
        warnings.warn(_DEPRECATED[name], DeprecationWarning, stacklevel=2)

    module = import_module(f".{module_name}", __name__)
    obj = getattr(module, attr_name)
    globals()[name] = obj  # memoize para chamadas futuras
    return obj


def __dir__() -> list[str]:
    # Reflete __all__ e símbolos já resolvidos (melhor DX em IDE)
    return sorted(list(set(list(globals().keys()) + list(__all__))))


# ---------------------------------------------------------------------------
# Caminhos opcionais:
# - Preload de essenciais: reduz latência no 1º acesso de hot-paths.
# - Strict imports: falha cedo se algum export não resolve (para CI).
# ---------------------------------------------------------------------------
def _preload_essentials() -> None:
    for name in _ESSENTIALS:
        # getattr dispara o lazy loader e deixa memoizado
        if name not in globals():
            _ = getattr(__import__(__name__, fromlist=[name]), name)


def _strict_validate_exports() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for name in __all__:
            if name not in globals():
                _ = getattr(__import__(__name__, fromlist=[name]), name)


if _env_flag("HSC_PRELOAD_ESSENTIALS"):
    _preload_essentials()

if _env_flag("HSC_STRICT_IMPORTS"):
    _strict_validate_exports()

# ---------------------------------------------------------------------------
# Suporte a type-checkers sem custo em runtime
# ---------------------------------------------------------------------------
if TYPE_CHECKING:
    from .circuit_breaker import CircuitBreaker  # noqa: F401
    from .circuit_breaker_manager import CircuitBreakerManager  # noqa: F401
    from .component_cache_manager import ComponentCacheManager  # noqa: F401
    from .global_health_service_manager import (  # noqa: F401
        GlobalHealthServiceManager,
        get_current_global_health_service,
        get_global_health_service,
        is_global_health_service_initialized,
        shutdown_global_health_service,
    )
    from .health_alerting import HealthAlerting  # noqa: F401
    from .health_check_retry import HealthCheckRetry  # noqa: F401
    from .health_check_service import HealthCheckService  # noqa: F401
    from .health_check_utils import HealthCheckUtils  # noqa: F401
    from .health_config_manager import HealthCheckConfigurationManager  # noqa: F401
    from .health_history_manager import HealthHistoryManager  # noqa: F401
    from .health_monitoring_coordinator import HealthMonitoringCoordinator  # noqa: F401
    from .health_service_manager import HealthServiceManager  # noqa: F401
    from .health_service_orchestrator import HealthServiceOrchestrator  # noqa: F401
    from .memory_manager import MemoryManager  # noqa: F401
    from .memory_usage_tracker import MemoryUsageTracker  # noqa: F401
    from .monitoring_aggregator import HealthMonitoringAggregator  # noqa: F401
    from .performance_metrics_collector import PerformanceMetricsCollector  # noqa: F401
    from .proactive_monitor import ProactiveHealthMonitor  # noqa: F401
    from .recovery_manager import HealthRecoveryManager  # noqa: F401




