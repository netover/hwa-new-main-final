# Resync: AI-Powered HWA/TWS Interface

## Overview
Resync is an AI-powered interface for HCL Workload Automation (HWA), formerly known as IBM Tivoli Workload Scheduler (TWS). It transforms complex TWS operations into an intuitive chat interface powered by artificial intelligence, providing real-time monitoring, status queries, and diagnostic capabilities in natural language.

## Portabilidade de Encoding no Windows

### Guia Rápido
1. **Ative UTF-8**: Use `PYTHONIOENCODING=utf-8` e `python -X utf8` para evitar UnicodeEncodeError.
2. **Evite emoji em logs críticos**: Use `symbol(ok, sys.stdout)` para fallback automático.
3. **Prefira Windows Terminal**: Suporte nativo a Unicode vs. cmd.exe/cp1252.
4. **Teste localmente**: Simule cp1252 para validar fallbacks.

### Sintoma → Causa → Correção

| Sintoma | Causa | Correção |
|---------|-------|----------|
| UnicodeEncodeError ao imprimir ✅/❌ | Console cp1252 não suporta emoji | Use `symbol(ok, sys.stdout)` ou force UTF-8 |
| Logs corrompidos em CI Windows | Encoding inconsistente | Adicione `PYTHONIOENCODING=utf-8` em CI |
| Emojis não aparecem | Terminal sem suporte Unicode | Use ASCII fallbacks ou Windows Terminal |
| Erros de encoding em testes | sys.stdout.encoding não UTF-8 | Configure PYTHONIOENCODING=utf-8 nos testes |

### Configuração Recomendada

#### PowerShell:
```powershell
$env:PYTHONIOENCODING="utf-8"
python -X utf8 -m pytest
```

#### cmd.exe:
```cmd
set PYTHONIOENCODING=utf-8
python -X utf8 -m pytest
```

#### CI/GitHub Actions:
```yaml
env:
  PYTHONIOENCODING: utf-8
```

#### Desenvolvimento Local:
```bash
# Ativar UTF-8
export PYTHONIOENCODING=utf-8
python -X utf8 -m resync.main

# Ou diretamente
PYTHONIOENCODING=utf-8 python -X utf8 -m resync.main
```

## 🚀 Performance & Security Optimizations

### Performance Enhancements

Resync has been optimized for high-performance production deployments:

- **Async-First Architecture**: Full asyncio implementation for non-blocking I/O
- **Connection Pooling**: Optimized database and Redis connection pools
- **Smart Caching**: Multi-layer caching with TTL and compression
- **Task Management**: Priority-based task scheduling with configurable workers
- **Memory Management**: Efficient memory usage with configurable limits

### Security Features

Comprehensive security hardening including:

- **Security Headers**: HSTS, CSP, X-Frame-Options, and more
- **Rate Limiting**: Configurable request limits with burst handling
- **Input Validation**: Comprehensive input sanitization and validation
- **Threat Protection**: User-agent blocking and path-based filtering
- **Cryptography**: Secure password hashing and token generation
- **Audit Logging**: Complete audit trail for security events

### ✅ Centralized Resilience Pattern

Resync now implements a **unified, production-grade resilience pattern** for all HTTP client operations:

- **CircuitBreakerManager**: Centralized registry-based circuit breaker using `pybreaker` (inspired by Resilience4j)
- **retry_with_backoff**: AWS-style exponential backoff with full jitter
- **Consistent Configuration**: All services use the same patterns, names, and parameters
- **Observability**: Circuit breaker states and metrics exposed for monitoring

**Implementation Examples:**
- `resync/services/rag_client.py`
- `resync/services/tws_service.py`

**New Service Requirement:**
> 🔒 **All new HTTP client services MUST use `CircuitBreakerManager` and `retry_with_backoff` from `resync/core/resilience.py`.**
> Custom circuit breaker or retry implementations are prohibited.

**CI/CD Enforcement:**
> A new quality gate has been added to the CI/CD pipeline to automatically fail builds that:
> - Use `@circuit_breaker` or `@retry_with_backoff` decorators directly
> - Implement custom retry or circuit breaker logic
> - Fail to register circuit breakers with `CircuitBreakerManager`

This ensures consistent, observable, and production-ready resilience across the entire codebase.

## 📊 Logging & Observability

### Sistema de Logs Estruturados

A aplicação utiliza um sistema avançado de logging estruturado com as seguintes características:

#### 📁 Arquivos de Log Gerados

**Estrutura de Diretórios:**
```
logs/
├── resync.log                    # Log principal (atual)
├── YYYYMMDD/                     # Diretório com data
│   └── resync.log               # Arquivo histórico
```

**Localização Atual:**
- **Diretório principal:** `logs/` (relativo à raiz do projeto)
- **Arquivo atual:** `logs/resync.log` (na raiz do diretório logs)
- **Arquivo histórico:** `logs/YYYYMMDD/resync.log` (diretório com data)

#### 🔄 Sistema de Log Rotate

**Configuração (RotatingFileHandler):**
```python
# resync/core/logger.py - linha 58-60
file_handler = RotatingFileHandler(
    log_dir / "resync.log",
    maxBytes=10 * 1024 * 1024,  # 10MB por arquivo
    backupCount=5               # Máximo 5 arquivos de backup
)
```

**Como Funciona:**
1. **Limite de tamanho:** Cada arquivo de log pode ter no máximo **10MB**
2. **Número de backups:** Mantém até **5 arquivos de backup**
3. **Rotação automática:** Quando o arquivo atual atinge 10MB, é automaticamente rotacionado
4. **Nomenclatura:** Arquivos rotacionados seguem padrão `resync.log.1`, `resync.log.2`, etc.
5. **Organização por data:** Logs são organizados em diretórios `YYYYMMDD` para fácil localização histórica

#### 📊 Formato dos Logs

**Exemplo de Log Estruturado (JSON):**
```json
{
  "timestamp": "2025-10-15T12:58:38.123456+00:00",
  "level": "info",
  "logger": "resync.app_factory",
  "message": "application_startup_completed",
  "component": "main",
  "correlation_id": null,
  "event": "LOG_EVENT"
}
```

#### ⚙️ Configuração de Logging

**Inicialização:**
- **Setup automático:** O logging é configurado automaticamente quando o módulo `environment_managers.py` é importado
- **Ambiente específico:** Cada ambiente (development, production, test) pode ter configurações diferentes
- **Nível configurável:** Via variável de ambiente `LOG_LEVEL` (padrão: INFO)

**Componentes:**
- **Structlog:** Para logs estruturados em JSON
- **RotatingFileHandler:** Para rotação automática de arquivos
- **Console Handler:** Saída simultânea no console/stdout

**Características Técnicas:**
- ✅ **Formato JSON:** Logs estruturados para fácil análise e monitoramento
- ✅ **Correlation IDs:** Rastreamento de requests através de IDs únicos
- ✅ **Rotação automática:** Gerenciamento inteligente de espaço em disco
- ✅ **Organização temporal:** Logs organizados por data para fácil localização
- ✅ **Métricas integradas:** Performance e métricas incluídas nos logs
- ✅ **Sanitização de dados:** Dados sensíveis são automaticamente mascarados

### Configuration

Performance and security settings are centralized in:
- `resync/core/performance_config.py` - Performance tuning
- `resync/core/security_hardening.py` - Security hardening
- `resync/core/constants.py` - Application constants

### Boas Práticas de Logging

- Use níveis de logging (INFO/ERROR) em vez de emoji para semântica
- Campos estruturados (`extra={'status': 'ok|err'}`) são preferíveis
- Emojis devem ser "nice-to-have" com fallback automático
- Teste logs em diferentes encodings antes de deploy

## Security Improvements

### Credential Management
- Removed hardcoded credentials from configuration files
- Implemented secure credential validation during startup
- Added requirements for environment-specific credential values

### Authentication System
- Implemented JWT-based authentication system
- Created proper login endpoint with secure credential validation
- Added CSRF protection and secure session management

### CORS Configuration Security
- Enhanced CORS configuration with strict validation
- Implemented per-environment CORS policies
- Added security monitoring for CORS violations

## Critical Reliability Fixes

### Redis Idempotency Initialization Security Fix

**🚨 CRITICAL SECURITY ISSUE RESOLVED**

**Problem:** The application previously used dangerous generic exception handling during Redis initialization for idempotency keys, silently falling back to in-memory storage when Redis was unavailable. This compromised data integrity and idempotency guarantees.

**Impact:**
- **Data Loss Risk**: Idempotency keys stored in volatile memory would be lost on application restart
- **Duplicate Operations**: Same operations could execute multiple times without proper tracking
- **Production Unsafety**: System appeared functional but couldn't guarantee critical business operations
- **Silent Failures**: No alerts when Redis connectivity issues occurred

**Solution Implemented:**
```python
# resync/lifespan.py - Redis initialization with atomic context management
@asynccontextmanager
async def redis_connection_manager() -> AsyncIterator:
    """
    Context manager to manage Redis connection with proper cleanup.

    Yields:
        Redis client connected and validated
    """
    from resync.core.async_cache import get_redis_client

    client = None
    try:
        client = await get_redis_client()
        await client.ping()  # Validate connection before yielding
        yield client
    finally:
        if client:
            try:
                await client.close()
                await client.connection_pool.disconnect()
            except Exception as e:
                logger.warning(
                    "redis_cleanup_failed",
                    error=type(e).__name__,
                    message=str(e)
                )

async def initialize_redis_with_retry(
    max_retries: int = 3,
    base_backoff: float = 0.1,
    max_backoff: float = 10.0
) -> None:
    """
    Initialize Redis with exponential backoff retry.

    Args:
        max_retries: Maximum number of attempts
        base_backoff: Base wait time in seconds
        max_backoff: Maximum wait time in seconds

    Raises:
        RedisStartupError: If failed after all attempts
    """
    # Environment validation
    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url:
        logger.critical("redis_url_not_configured")
        raise RedisStartupError("REDIS_URL environment variable not set")

    # Startup metrics tracking
    startup_metrics = {
        "attempts": 0,
        "connection_failures": 0,
        "auth_failures": 0,
        "duration_seconds": 0.0
    }

    start_time = asyncio.get_event_loop().time()

    for attempt in range(max_retries):
        startup_metrics["attempts"] += 1

        try:
            async with redis_connection_manager() as redis_client:
                # Initialize idempotency manager
                from resync.api.dependencies import initialize_idempotency_manager
                await initialize_idempotency_manager(redis_client)

                # Success
                startup_metrics["duration_seconds"] = (
                    asyncio.get_event_loop().time() - start_time
                )

                logger.info(
                    "redis_initialized_successfully",
                    metrics=startup_metrics,
                    duration_ms=int(startup_metrics["duration_seconds"] * 1000)
                )
                return

        except (ConnectionError, TimeoutError, BusyLoadingError) as e:
            startup_metrics["connection_failures"] += 1

            if attempt >= max_retries - 1:
                logger.critical(
                    "redis_initialization_failed",
                    reason="max_retries_exceeded",
                    metrics=startup_metrics,
                    error_type=type(e).__name__
                )
                raise RedisStartupError(
                    f"Redis unavailable after {max_retries} attempts"
                ) from e

            # Exponential backoff
            backoff = min(max_backoff, base_backoff * (2 ** attempt))
            logger.warning(
                "redis_connection_retry",
                attempt=attempt + 1,
                max_retries=max_retries,
                backoff_seconds=backoff,
                error_type=type(e).__name__
            )
            await asyncio.sleep(backoff)

        except AuthenticationError as e:
            startup_metrics["auth_failures"] += 1
            logger.critical(
                "redis_authentication_failed",
                metrics=startup_metrics,
                error_type=type(e).__name__
            )
            raise RedisStartupError("Redis authentication failed") from e

        except ResponseError as e:
            # Handle ACL/permission errors
            error_msg = str(e).upper()
            if "NOAUTH" in error_msg or "WRONGPASS" in error_msg:
                startup_metrics["auth_failures"] += 1
                logger.critical(
                    "redis_access_denied",
                    metrics=startup_metrics,
                    error_type=type(e).__name__
                )
                raise RedisStartupError("Redis access denied") from e
            else:
                # Other ResponseError - try retry
                if attempt >= max_retries - 1:
                    logger.critical(
                        "redis_response_error",
                        metrics=startup_metrics,
                        error_type=type(e).__name__
                    )
                    raise RedisStartupError(
                        f"Redis error: {type(e).__name__}"
                    ) from e

                backoff = min(max_backoff, base_backoff * (2 ** attempt))
                await asyncio.sleep(backoff)

        except Exception as e:
            # Unexpected error - fail fast
            logger.critical(
                "redis_unexpected_error",
                error_type=type(e).__name__,
                # Don't include details in production
                message=str(e) if settings.ENVIRONMENT != "production" else None
            )
            raise RedisStartupError(f"Unexpected error: {type(e).__name__}") from e
```

**Key Improvements:**
- **Atomic Context Management**: Uses `asynccontextmanager` to ensure Redis connection validation and cleanup are atomic
- **Connection Pre-Validation**: `ping()` is called within the context manager before yielding the client
- **Comprehensive Exception Handling**: Specific handling for all Redis exception types
- **Exponential Backoff**: Intelligent retry strategy (0.1s → 0.2s → 0.4s → 0.8s → 1.6s → 3.2s → 6.4s → 10s)
- **Startup Metrics**: Detailed tracking of attempts, failures, and timing
- **Fail-Fast Strategy**: Terminates application when Redis is unavailable
- **Resource Cleanup**: Automatic connection cleanup even on failures
- **Environment Awareness**: Development mode skips Redis if unavailable

**Production Requirements:**
> ⚠️ **CRITICAL**: Redis must be available and properly configured. If Redis is unavailable during startup, the application will terminate with exit code 1 to prevent operating in an unsafe degraded mode. This ensures idempotency guarantees are maintained for all critical operations.

**Additional Production Features:**

- **Startup Metrics Tracking**: Records connection attempts, failures, duration, and success rates
- **Environment Validation**: Validates REDIS_URL configuration before connection attempts
- **Health Check Endpoints**: `/api/health/redis` and `/api/health/app` for Redis status validation
- **Development Mode Fallback**: In development, Redis unavailability doesn't crash the app
- **Structured Logging**: All events logged with correlation and detailed context
- **Connection Pool Management**: Proper Redis connection pool lifecycle management

**Benefits:**
- ✅ **Race Condition Prevention**: Atomic connection validation and initialization
- ✅ **Thundering Herd Mitigation**: Exponential backoff prevents simultaneous reconnections
- ✅ **Split-Brain Protection**: Connection validation before critical operations
- ✅ **Data Integrity**: Idempotency keys persist across application restarts
- ✅ **Operational Safety**: No duplicate critical operations
- ✅ **Production Readiness**: Clear failure modes with proper alerting
- ✅ **Observability**: Detailed logging and metrics for troubleshooting
- ✅ **Compliance**: Meets requirements for financial/payment system reliability
- ✅ **Resource Safety**: Automatic cleanup prevents connection leaks
- ✅ **Performance Monitoring**: Startup metrics for optimization

## Performance Optimizations

### Phase 2: Advanced Performance Optimization ✅ COMPLETE

**Status:** Fully implemented and tested

Phase 2 introduces comprehensive performance monitoring, optimization, and resource management capabilities:

#### 🚀 Key Features

1. **Performance Monitoring Service**
   - Real-time cache performance tracking
   - Connection pool optimization
   - Resource usage monitoring
   - Automatic efficiency scoring

2. **Resource Management**
   - Context managers for deterministic cleanup
   - Automatic resource tracking
   - Leak detection with configurable thresholds
   - Batch resource operations

3. **REST API Endpoints**
   - `/api/performance/health` - Overall health status
   - `/api/performance/report` - Comprehensive performance report
   - `/api/performance/cache/metrics` - Cache performance metrics
   - `/api/performance/pools/metrics` - Connection pool statistics
   - `/api/performance/resources/leaks` - Resource leak detection
   - And more...

4. **Auto-Tuning Recommendations**
   - Automatic cache optimization suggestions
   - Connection pool sizing recommendations
   - Performance improvement tips

#### 📊 Expected Improvements

- **30-50% reduction** in database queries (with optimized caching)
- **40-60% reduction** in connection overhead
- **Sub-10ms** cache access times
- **Zero resource leaks** with proper usage

#### 🎯 Quick Start

```bash
# Verify implementation
python test_phase2_simple.py

# Start the application
uvicorn resync.main:app --reload

# Check performance health
curl http://localhost:8000/api/performance/health

# Get full performance report
curl http://localhost:8000/api/performance/report
```

#### 📚 Documentation

- **Quick Reference:** [docs/PERFORMANCE_QUICK_REFERENCE.md](docs/PERFORMANCE_QUICK_REFERENCE.md)
- **Full Guide:** [docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md)
- **Testing & Deployment:** [docs/TESTING_DEPLOYMENT_GUIDE.md](docs/TESTING_DEPLOYMENT_GUIDE.md)

### AsyncTTLCache Improvements
- Enhanced memory management with better size estimation
- Implemented LRU eviction when cache bounds are exceeded
- Added more accurate memory usage tracking
- Memory bounds checking (100K items, 100MB limit)
- Hit rate monitoring and efficiency scoring

### Connection Pool Optimization
- Improved Redis connection pool settings
- Enhanced database connection pool configuration
- Optimized HTTP connection pool for external API calls
- Performance monitoring and auto-tuning
- Health status tracking

### Resource Management
- Added centralized resource manager for proper lifecycle management
- Implemented proper shutdown and cleanup procedures
- Enhanced resource tracking and monitoring
- Context managers for automatic cleanup
- Leak detection capabilities

## Error Handling Improvements

### Standardized Error Handling Patterns
- Created consistent error handling across all components
- Implemented proper exception hierarchies
- Standardized error response formats

### API Error Responses
- Implemented comprehensive error response models
- Added troubleshooting hints to error responses
- Enhanced logging with correlation IDs

## Code Quality Enhancements

### Code Duplication Removal
- Created shared utility modules for common functionality
- Implemented reusable error handling decorators
- Centralized common patterns

### Function Complexity Reduction
- Broke down complex functions into smaller, manageable pieces
- Improved maintainability and readability
- Enhanced testability of components

### Type Annotation Improvements
- Added comprehensive type annotations throughout the codebase
- Enhanced type safety with proper generics
- Improved IDE support and static analysis

## Architectural Improvements

### Dependency Injection System
- Enhanced service registration and resolution
- Added better error handling for missing services
- Improved factory functions for complex dependencies

### Middleware Optimization
- Added performance monitoring to error handler middleware
- Enhanced logging and correlation tracking
- Improved security monitoring

## New Features and Enhancements

### Monitoring and Metrics
- Added comprehensive error metrics tracking
- Enhanced runtime metrics collection
- Implemented Prometheus-compatible metrics endpoint

### Security Enhancements
- Enhanced CSP middleware with better reporting
- Added detailed security headers
- Improved input validation and sanitization

## Configuration

### Environment Variables
The application requires the following environment variables:

```
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_secure_admin_password
SECRET_KEY=your_very_secure_random_string_at_least_32_chars_long
REDIS_URL=redis://your-redis-host:6379
LLM_ENDPOINT=http://your-llm-endpoint:11434/v1
LLM_API_KEY=your_llm_api_key
TWS_HOST=your-tws-host
TWS_PORT=31111
TWS_USER=your-tws-username
TWS_PASSWORD=your-tws-password
```

### Settings Configuration
The application uses a hierarchical configuration system with:
- Base settings in `settings.toml`
- Environment-specific overrides in `settings.{environment}.toml`
- Environment variables with `APP_` prefix

## Architecture

Resync follows a modern, modular architecture designed for scalability, security, and maintainability. The system is built around FastAPI with dependency injection, comprehensive error handling, and advanced caching capabilities.

### Core Components

#### Entry Points
- **`resync/main.py`** - Primary application entry point
  - Creates and configures the FastAPI application
  - Sets up middleware, routes, and dependency injection
  - Handles application lifecycle events

- **`resync/app_factory.py`** - Application factory with lifespan management
  - Creates and configures the FastAPI application instance
  - Manages application startup and shutdown lifecycle
  - Configures middleware, routes, error handling, and static files
  - Implements atomic Redis initialization with retry logic
  - Validates critical settings before startup

#### Application Factory Pattern
The application uses a sophisticated factory pattern with lifespan management:

```python
# resync/app_factory.py - Lifespan management with Redis initialization
@asynccontextmanager
async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
    # Startup: Initialize Redis, services, and dependencies
    await initialize_redis_with_retry()
    # ... other initialization logic

    yield  # Application runs here

    # Shutdown: Cleanup resources
    await shutdown_services()

def create_application(self) -> FastAPI:
    """Create fully configured FastAPI application."""
    app = FastAPI(lifespan=self.lifespan)
    # Configure all components in proper order
    return app
```

#### Dependency Injection System
The system uses a comprehensive dependency injection container:
- **`resync/core/container.py`** - Main DI container with async service resolution
- **`resync/core/interfaces.py`** - Service interfaces for dependency inversion
- **`resync/api/dependencies.py`** - Request-scoped dependencies and idempotency management
- Services are registered and resolved through the container for testability

#### Advanced Caching Layer
- **`resync/core/async_cache.py`** - High-performance async TTL cache with Redis backend
- **`resync/core/cache_manager.py`** - Multi-level cache management (memory + Redis)
- **`resync/core/memory_bounds.py`** - Memory-bounded cache with automatic eviction
- **`resync/core/connection_pool_manager.py`** - Optimized connection pool management

#### Security Layer
- **CSP Validation** - Content Security Policy with nonce support
- **Authentication** - JWT-based authentication with secure session management
- **CORS Configuration** - Environment-specific CORS policies with monitoring
- **Input Validation** - Pydantic models with comprehensive validation
- **Rate Limiting** - Redis-backed rate limiting with idempotency

### Running the Application

#### Development Mode
```bash
uvicorn resync.main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Deployment
```bash
# Using uvicorn directly
uvicorn resync.main:app --host 0.0.0.0 --port 8000 --workers 4

# Using gunicorn with uvicorn workers
gunicorn resync.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

#### Docker Deployment
```bash
docker build -t resync .
docker run -p 8000:8000 \
  -e REDIS_URL=redis://redis:6379 \
  -e ADMIN_PASSWORD=secure_password \
  resync
```

### Component Architecture

#### API Layer (`resync/api/`)
- **Endpoints** - REST API routes with automatic OpenAPI generation
- **Middleware** - Request/response processing pipeline
- **Dependencies** - Request-scoped dependency injection
- **Exception Handlers** - Centralized error handling and responses
- **Rate Limiting** - Per-endpoint rate limiting with Redis

#### Core Services (`resync/core/`)
- **Agent Manager** - AI agent lifecycle and coordination
- **Cache System** - Multi-level caching with performance monitoring
- **Connection Pools** - Optimized database and Redis connection management
- **Structured Logger** - Correlated logging with performance metrics
- **Resource Manager** - Automatic resource cleanup and leak detection

#### CQRS Architecture (`resync/cqrs/`)
- **Commands** - Write operations with validation and idempotency
- **Queries** - Read operations with caching and optimization
- **Dispatcher** - Command/query routing and execution
- **Event Sourcing** - Optional event-driven architecture support

#### External Integrations (`resync/services/`)
- **TWS Client** - HCL Workload Automation integration
- **LLM Integration** - AI model providers (LiteLLM)
- **Knowledge Graph** - Graph database for complex relationships

### Advanced Features

#### Performance Monitoring
- Real-time metrics collection
- Cache efficiency scoring
- Connection pool monitoring
- Resource leak detection
- Auto-tuning recommendations

#### Idempotency System
- Redis-backed operation deduplication
- Configurable TTL for idempotency keys
- Atomic operation guarantees
- Production-safe fail-fast initialization

#### Structured Logging
- Correlation ID tracking across requests
- Performance metrics in logs
- Structured JSON output for monitoring
- Environment-aware log levels

## API Endpoints

### Authentication & Admin
- `GET /login` - Login page for admin access
- `POST /token` - OAuth2 token endpoint for JWT authentication
- `GET /admin` - Main admin dashboard interface
- `GET /revisao` - System revision and audit interface

### Health & Monitoring
- `GET /api/health/app` - Application health check with Redis status
- `GET /api/health/tws` - TWS connection health check
- `GET /api/health/redis` - Redis connectivity and idempotency safety check
- `GET /api/health/full` - Comprehensive system health report

### Core Functionality
- `GET /api/status` - Comprehensive TWS system status
- `POST /api/chat` - Chat endpoint for natural language queries
- `GET /api/agents` - List all configured agents
- `GET /api/agents/{id}` - Get specific agent details

### Performance & Monitoring
- `GET /api/performance/health` - Overall performance health status
- `GET /api/performance/report` - Comprehensive performance report
- `GET /api/performance/cache/metrics` - Cache performance metrics
- `GET /api/performance/pools/metrics` - Connection pool statistics
- `GET /api/performance/resources/leaks` - Resource leak detection
- `GET /api/performance/recommendations` - Auto-tuning recommendations

### Cache Management
- `GET /api/cache/stats` - Cache statistics and hit rates
- `POST /api/cache/clear` - Clear cache (admin only)
- `GET /api/cache/health` - Cache health and connectivity

### Audit & Security
- `GET /api/audit/events` - Audit event log
- `GET /api/audit/report` - Security audit report
- `GET /api/cors/violations` - CORS violation monitoring
- `POST /csp-violation-report` - CSP violation reporting endpoint

### Metrics & Observability
- `GET /api/metrics` - Prometheus-compatible metrics endpoint
- `GET /api/metrics/performance` - Performance metrics
- `GET /api/metrics/security` - Security metrics

### Static Resources
- `GET /static/*` - Static file serving with caching
- `GET /assets/*` - Asset file serving
- `GET /css/*` - CSS file serving
- `GET /js/*` - JavaScript file serving

## Security Features

- JWT-based authentication for API access
- Content Security Policy (CSP) headers
- CORS with strict origin validation
- Input validation and sanitization
- Rate limiting with Redis backend
- Comprehensive request logging with correlation IDs

## Contributing

We welcome contributions to improve Resync! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper testing
4. Submit a pull request with a clear description

## Technologies & Dependencies

### Core Framework
- **FastAPI** - High-performance async web framework
- **Uvicorn** - ASGI server implementation
- **Pydantic v2** - Data validation and serialization
- **Starlette** - ASGI toolkit for building async apps

### Caching & Performance
- **Redis** - High-performance key-value store
- **AsyncTTL** - Time-based cache with automatic expiration
- **Memory Bounds** - Memory-constrained cache management
- **Connection Pools** - Optimized connection management

#### Redis Initialization
The `RedisInitializer` provides robust Redis connection management with:
- Thread-safe initialization
- Exponential backoff retry logic
- Distributed locking mechanism
- Connection validation
- Comprehensive health check loop

Example configuration:
```python
# In settings.toml or environment variables
redis_max_startup_retries = 3
redis_startup_backoff_base = 0.1
redis_startup_backoff_max = 10.0
redis_startup_lock_timeout = 30
redis_health_check_interval = 5
```

#### Robust Cache Manager
The `RobustCacheManager` offers advanced caching capabilities:
- Accurate deep size calculation
- LRU (Least Recently Used) eviction strategy
- Configurable memory and item limits
- Weak references for large objects
- Write-Ahead Logging (WAL) support
- Comprehensive metrics collection

Example configuration:
```python
# In settings.toml or environment variables
robust_cache_max_items = 100_000
robust_cache_max_memory_mb = 100
robust_cache_eviction_batch_size = 100
robust_cache_enable_weak_refs = true
robust_cache_enable_wal = false
robust_cache_wal_path = "./cache_wal"
```

### Security & Authentication
- **PyJWT** - JSON Web Token implementation
- **Passlib** - Password hashing utilities
- **Cryptography** - Cryptographic primitives

### External Integrations
- **LiteLLM** - Unified interface for LLM providers
- **HCL TWS Client** - Workload Automation integration
- **Knowledge Graph** - Graph database integration

### Development & Testing
- **Pytest** - Testing framework with async support
- **Black** - Code formatting
- **MyPy** - Static type checking
- **Pylint** - Code quality analysis

### Monitoring & Observability
- **Structured Logging** - JSON-formatted logs with correlation IDs
- **Prometheus Metrics** - Performance and health metrics
- **Health Checks** - Comprehensive system health monitoring

## Contributing

We welcome contributions to improve Resync! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper testing
4. Run the test suite (`pytest`)
5. Format code (`black .`)
6. Check types (`mypy .`)
7. Run linters (`pylint resync/`, `flake8 resync/`)
8. Commit your changes (`git commit -m 'Add amazing feature'`)
9. Push to the branch (`git push origin feature/amazing-feature`)
10. Submit a pull request with a clear description

### Development Setup

**Requirements:**
- Python 3.13 or later
- Dependencies from `requirements/dev.txt` (development) or `requirements/prod.txt` (production)

```bash
# Clone the repository
git clone https://github.com/your-org/resync.git
cd resync

# Install dependencies (development)
pip install -r requirements/dev.txt

# Set up environment variables
cp settings.development.toml.example settings.development.toml
# Edit settings.development.toml with your configuration

# Run tests
pytest

# Format code with Black
black .

# Check types with MyPy
mypy .

# Run linters
pylint resync/
flake8 resync/

# Start development server
uvicorn resync.main:app --reload
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
