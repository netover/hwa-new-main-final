from typing import Any, Dict

_LAZY_API_EXPORTS: Dict[str, tuple[str, str]] = {
    "create_app": ("resync.api.app_factory", "create_app"),
    "router": ("resync.api.app_factory", "router"),
    "register_routes": ("resync.api.routes", "register_routes"),
}
_LOADED: Dict[str, Any] = {}

def __getattr__(name: str):
    if name in _LAZY_API_EXPORTS:
        mod, attr = _LAZY_API_EXPORTS[name]
        if name not in _LOADED:
            module = __import__(mod, fromlist=[attr])
            _LOADED[name] = getattr(module, attr)
        return _LOADED[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")