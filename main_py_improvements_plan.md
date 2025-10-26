# Resync Main.py Improvements Implementation Plan

## Overview
This document outlines the specific improvements needed for `resync/main.py` to make it production-ready based on the recommendations provided.

## Current Issues Identified

1. **_check_tcp function is not fully async**: Uses `loop.run_in_executor(None, _connect)` instead of native async operations
2. **Cache reset issue in cleanup_resources()**: Missing `global` declaration for `_validated_settings_cache`
3. **fail_fast parameter not respected**: `get_validated_settings()` doesn't pass `fail_fast` to `validate_configuration_on_startup()`
4. **Exception handling incomplete**: `StartupError` not included in exception handling tuple
5. **HEAD request may cause 405 errors**: Some APIs don't support HEAD requests
6. **Signal handlers use sys.exit()**: Should use `server.should_exit = True` for graceful shutdown

## Detailed Improvements Required

### 1. Implement 100% async _check_tcp using asyncio.open_connection

**Current Implementation (Lines 117-127):**
```python
async def _check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """Asynchronously check if a TCP port is open."""
    def _connect() -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _connect)
```

**Improved Implementation:**
```python
async def _check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """
    Verifica reachability TCP de forma 100% assíncrona.
    Usa asyncio.open_connection com timeout explícito.
    """
    try:
        await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        return True
    except Exception:
        return False
```

### 2. Fix cache reset in cleanup_resources()

**Current Implementation (Lines 251-267):**
```python
def cleanup_resources() -> None:
    """
    Perform cleanup of application resources.

    Called during graceful shutdown to ensure proper resource cleanup.
    """
    try:
        startup_logger.info("performing_resource_cleanup")

        # Clear validated settings cache
        # Clear the settings cache
        _validated_settings_cache = None

        startup_logger.info("resource_cleanup_completed")

    except Exception as e:
        startup_logger.error("resource_cleanup_failed", error=str(e))
```

**Improved Implementation:**
```python
def cleanup_resources() -> None:
    """Limpa recursos de aplicação (cache de settings, etc.)."""
    try:
        startup_logger.info("performing_resource_cleanup")
        # ✅ Corrige limpeza do cache global
        global _validated_settings_cache
        _validated_settings_cache = None
        startup_logger.info("resource_cleanup_completed")
    except Exception as e:
        startup_logger.error("resource_cleanup_failed", error=str(e))
```

### 3. Update get_validated_settings() to respect fail_fast parameter

**Current Implementation (Lines 93-114):**
```python
async def get_validated_settings(fail_fast: bool = True) -> "Settings":
    """
    Cached settings validation to avoid repeated checks.

    This function caches the validated settings to prevent redundant
    validation operations during application lifecycle.

    Returns:
        Validated Settings object

    Raises:
        Reraises exceptions from validate_configuration_on_startup if fail_fast is False.
    """
    global _validated_settings_cache

    async with _settings_validation_lock:
        if _validated_settings_cache is None:
            startup_logger.info("performing_initial_settings_validation")
            _validated_settings_cache = await validate_configuration_on_startup()
            startup_logger.info("settings_validation_cached_successfully")

        return _validated_settings_cache
```

**Improved Implementation:**
```python
async def get_validated_settings(fail_fast: bool = True) -> "Settings":
    """Valida e cacheia Settings (fail-fast configurável)."""
    global _validated_settings_cache
    async with _settings_validation_lock:
        if _validated_settings_cache is None:
            startup_logger.info("performing_initial_settings_validation")
            # ✅ respeita fail_fast
            _validated_settings_cache = await validate_configuration_on_startup(fail_fast=fail_fast)
            startup_logger.info("settings_validation_cached_successfully")
        return _validated_settings_cache
```

### 4. Adjust exception handling to include StartupError

**Current Implementation (Lines 319-372):**
```python
except (ConfigurationValidationError, DependencyUnavailableError) as e:
    # Handle different types of validation errors with appropriate logging
    if isinstance(e, ConfigurationValidationError):
        # ... logging code
    elif isinstance(e, DependencyUnavailableError):
        # ... logging code
    elif isinstance(e, StartupError):
        # ... logging code
    else:
        # Fallback for unexpected errors
        # ... logging code
```

**Improved Implementation:**
```python
except (ConfigurationValidationError, DependencyUnavailableError, StartupError) as e:
    # ✅ StartupError agora tratado aqui
    if isinstance(e, ConfigurationValidationError):
        startup_logger.error("configuration_validation_failed",
                             error_type="ConfigurationValidationError",
                             error_message=e.message, error_details=e.details,
                             status_symbol=symbol(False, sys.stdout))
    elif isinstance(e, DependencyUnavailableError):
        startup_logger.error("dependency_unavailable",
                             error_type="DependencyUnavailableError",
                             dependency=e.dependency, error_message=e.message,
                             error_details=e.details, status_symbol=symbol(False, sys.stdout))
    else:
        startup_logger.error("startup_error",
                             error_type="StartupError",
                             error_message=getattr(e, "message", str(e)),
                             error_details=getattr(e, "details", None),
                             status_symbol=symbol(False, sys.stdout))
```

### 5. Change HEAD to GET in LLM health check

**Current Implementation (Lines 172-185):**
```python
# LLM service basic check (if endpoint is configured)
if hasattr(settings, 'llm_endpoint') and settings.llm_endpoint:
    try:
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Simple HEAD request to check if service is responsive
            async with session.head(settings.llm_endpoint.rstrip('/')) as response:
                health_results["llm_service"] = response.status < 500
    except aiohttp.ClientError as e:
        startup_logger.warning("llm_service_check_failed", error=str(e))
        health_results["llm_service"] = False
    except Exception as e:
        startup_logger.warning("llm_service_check_unexpected_error", error=str(e))
        health_results["llm_service"] = False
```

**Improved Implementation:**
```python
# LLM service basic check (GET curto; HEAD pode retornar 405 em alguns provedores)
if getattr(settings, 'llm_endpoint', None):
    try:
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(settings.llm_endpoint.rstrip('/'), allow_redirects=True) as resp:
                health_results["llm_service"] = resp.status < 500
    except aiohttp.ClientError as e:
        startup_logger.warning("llm_service_check_failed", error=str(e))
        health_results["llm_service"] = False
    except Exception as e:
        startup_logger.warning("llm_service_check_unexpected_error", error=str(e))
        health_results["llm_service"] = False
```

### 6. Update signal handlers to use server.should_exit = True

**Current Implementation (Lines 227-240):**
```python
def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    signal_name = signal.Signals(signum).name
    startup_logger.info(
        "shutdown_signal_received",
        signal=signal_name,
        signal_number=signum
    )

    # Perform cleanup
    cleanup_resources()

    startup_logger.info("application_shutdown_complete")
    sys.exit(0)
```

**Improved Implementation:**
This requires restructuring the signal handling to work with Uvicorn's server object:

```python
def setup_signal_handlers(server: Optional[uvicorn.Server] = None) -> None:
    """Configura handlers para SIGTERM/SIGINT (apenas main thread; skip no Windows)."""
    if platform.system() == "Windows":
        startup_logger.debug("signal_handlers_skipped_on_windows")
        return
    if threading.current_thread() is not threading.main_thread():
        startup_logger.debug("signal_handlers_skipped_on_non_main_thread")
        return

    def signal_handler(signum: int, frame: Any) -> None:
        signal_name = signal.Signals(signum).name
        startup_logger.info("shutdown_signal_received", signal=signal_name, signal_number=signum)
        cleanup_resources()
        startup_logger.info("application_shutdown_complete")
        
        # Prefer server.should_exit = True over sys.exit() when server is available
        if server is not None:
            server.should_exit = True
        else:
            sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        startup_logger.info("signal_handlers_configured_successfully")
    except (ValueError, OSError) as e:
        startup_logger.warning("could_not_set_signal_handlers", reason=str(e))
```

And update the main() function to pass the server object:

```python
# Start the server
config = uvicorn.Config(
    app,
    host=getattr(settings, "server_host", "127.0.0.1"),
    port=getattr(settings, "server_port", 8000),
    log_config=None,   # usar nosso logging estruturado
    access_log=False,  # logs de acesso via middleware, se necessário
)
server = uvicorn.Server(config)

# Setup signal handlers with server reference
setup_signal_handlers(server)

await server.serve()
```

## Implementation Priority

1. **High Priority**: Fix cache reset and fail_fast parameter (critical functionality)
2. **Medium Priority**: Implement 100% async _check_tcp and fix exception handling
3. **Medium Priority**: Change HEAD to GET in LLM health check
4. **Low Priority**: Update signal handlers (requires restructuring)

## Testing Strategy

1. **Unit Tests**: Test each improved function individually
2. **Integration Tests**: Test startup flow with all improvements
3. **Error Scenarios**: Test failure modes and exception handling
4. **Performance Tests**: Verify async improvements don't degrade performance

## Compatibility Considerations

- All changes maintain backward compatibility
- Function signatures remain the same where possible
- Error handling is enhanced but doesn't break existing error flows
- Logging format and structure remain consistent

## Production Readiness Benefits

1. **Better Async Performance**: Native async operations instead of thread pool
2. **Proper Resource Management**: Correct cache cleanup prevents memory leaks
3. **Configurable Fail-Fast**: Allows flexible startup behavior
4. **Robust Error Handling**: Comprehensive exception coverage
5. **Better API Compatibility**: GET requests work with more LLM providers
6. **Graceful Shutdown**: Proper server shutdown handling

## Next Steps

1. Implement all improvements in the code
2. Run comprehensive tests
3. Update documentation if needed
4. Deploy to staging environment for validation
5. Monitor for any issues in production