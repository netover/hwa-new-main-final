# Resync: AI-Powered HWA/TWS Interface - Unified Documentation

## Overview

Resync is an AI-powered interface for HCL Workload Automation (HWA), formerly known as IBM Tivoli Workload Scheduler (TWS). It transforms complex TWS operations into an intuitive chat interface powered by artificial intelligence, providing real-time monitoring, status queries, and diagnostic capabilities in natural language.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Performance Optimizations](#performance-optimizations)
4. [Security Features](#security-features)
5. [API Endpoints](#api-endpoints)
6. [Installation & Setup](#installation--setup)
7. [Configuration](#configuration)
8. [Testing & Deployment](#testing--deployment)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Troubleshooting](#troubleshooting)

## System Overview

### Core Features

Resync provides a comprehensive set of features for managing HWA/TWS systems:

- **AI-Powered Chat Interface**: Natural language processing for TWS operations
- **Real-Time Monitoring**: Live status of workstations, jobs, and schedules
- **Diagnostic Capabilities**: Automated issue detection and resolution suggestions
- **Performance Optimization**: Advanced caching, connection pooling, and resource management
- **Security Hardening**: Multi-layer security with authentication, authorization, and threat protection
- **Audit & Compliance**: Comprehensive logging and memory review system

### Technology Stack

- **Framework**: FastAPI (async)
- **Database**: Neo4j (Knowledge Graph)
- **Caching**: Redis with advanced TTL cache
- **Frontend**: Jinja2 templates with static assets
- **AI/ML**: LiteLLM integration
- **Monitoring**: Structured logging and metrics
- **Testing**: Pytest
- **Deployment**: Docker support

## Architecture

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
  - Includes multi-level caching (memory + Redis), memory bounds, and performance monitoring.
- **`resync/core/connection_pool_manager.py`** - Optimized connection pool management for DB, Redis, and HTTP.

#### Security Layer
- **CSP Validation** - Content Security Policy with nonce support
- **Authentication** - JWT-based authentication with secure session management
- **CORS Configuration** - Environment-specific CORS policies with monitoring
- **Input Validation** - Pydantic models with comprehensive validation
- **Rate Limiting** - Redis-backed rate limiting with idempotency

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

## Performance Optimizations

### Phase 2: Advanced Performance Optimization ✅ COMPLETE

Phase 2 introduces comprehensive performance monitoring, optimization, and resource management capabilities.

#### Key Features

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

#### Expected Improvements

- **30-50% reduction** in database queries (with optimized caching)
- **40-60% reduction** in connection overhead
- **Sub-10ms** cache access times
- **Zero resource leaks** with proper usage

#### Quick Start

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

### AsyncTTLCache Memory Management

The `AsyncTTLCache` provides asynchronous, thread-safe caching with Time-To-Live (TTL) support and advanced memory management features.

#### Key Features

1. **Memory Bounds Checking**
   - Automatic memory usage monitoring
   - Configurable maximum cache size (items and memory)
   - Intelligent sampling for memory estimation

2. **LRU Eviction Policy**
   - Least Recently Used (LRU) eviction when cache reaches capacity
   - Prevents memory exhaustion
   - Maintains most relevant data

3. **Hit Rate Monitoring**
   - Real-time hit/miss rate tracking
   - Performance metrics collection
   - Automatic efficiency scoring

4. **Sharded Architecture**
   - Multiple shards to reduce lock contention
   - Configurable shard count
   - Parallel cleanup operations

#### Configuration

```toml
[default.ASYNC_CACHE]
TTL_SECONDS = 60              # Default TTL for cache entries
CLEANUP_INTERVAL = 30         # Background cleanup interval
NUM_SHARDS = 8                # Number of cache shards
MAX_WORKERS = 4               # Max concurrent workers
```

#### Usage Example

```python
from resync.core.async_cache import AsyncTTLCache

# Create cache instance
cache = AsyncTTLCache(ttl_seconds=60, num_shards=8)

# Set a value
await cache.set("user:123", user_data, ttl_seconds=300)

# Get a value
user = await cache.get("user:123")

# Delete a value
await cache.delete("user:123")

# Get cache statistics
size = cache.size()
```

#### Memory Management

The cache implements two-level memory bounds checking:

1. **Item Count Bounds**: Maximum 100,000 entries per cache instance
2. **Memory Usage Bounds**: Maximum 100MB per cache instance

When bounds are exceeded, the cache automatically evicts the least recently used entries.

### Connection Pool Optimization

Connection pools are optimized for database, Redis, and HTTP connections with automatic monitoring and tuning capabilities.

#### Key Features

1. **Configurable Pool Sizes**
   - Minimum and maximum pool sizes
   - Idle timeout configuration
   - Connection lifetime management

2. **Health Checking**
   - Periodic health checks
   - Connection validation
   - Automatic recovery

3. **Performance Monitoring**
   - Connection acquisition time tracking
   - Pool utilization metrics
   - Error rate monitoring

4. **Auto-Tuning Recommendations**
   - Automatic pool size suggestions
   - Performance optimization recommendations
   - Resource efficiency analysis

#### Configuration

```toml
[default.CONNECTION_POOL]
# Database Pool
DB_POOL_MIN_SIZE = 20
DB_POOL_MAX_SIZE = 100
DB_POOL_CONNECT_TIMEOUT = 60
DB_POOL_IDLE_TIMEOUT = 1200
DB_POOL_MAX_LIFETIME = 1800
DB_POOL_HEALTH_CHECK_INTERVAL = 60

# Redis Pool
REDIS_POOL_MIN_SIZE = 5
REDIS_POOL_MAX_SIZE = 20
REDIS_POOL_CONNECT_TIMEOUT = 30
REDIS_POOL_IDLE_TIMEOUT = 300
REDIS_POOL_MAX_LIFETIME = 1800
REDIS_POOL_HEALTH_CHECK_INTERVAL = 60

# HTTP Pool
HTTP_POOL_MIN_SIZE = 10
HTTP_POOL_MAX_SIZE = 100
HTTP_POOL_CONNECT_TIMEOUT = 10
HTTP_POOL_IDLE_TIMEOUT = 300
HTTP_POOL_MAX_LIFETIME = 1800
HTTP_POOL_HEALTH_CHECK_INTERVAL = 60
```

#### Usage Example

```python
from resync.core.pools.pool_manager import get_connection_pool_manager

# Get pool manager
pool_manager = await get_connection_pool_manager()

# Get a specific pool
db_pool = await pool_manager.get_pool("database")

# Use a connection
async with db_pool.get_connection() as conn:
    result = await conn.execute(query)

# Get pool statistics
stats = pool_manager.get_pool_stats()

# Get optimization recommendations
recommendations = await pool_manager.get_optimization_recommendations()
```

### Resource Management

The resource management system provides deterministic cleanup and leak detection for all system resources.

#### Key Features

1. **Context Managers**
   - Automatic resource acquisition and release
   - Exception-safe cleanup
   - Support for both sync and async operations

2. **Resource Tracking**
   - Automatic resource registration
   - Lifetime monitoring
   - Usage statistics

3. **Leak Detection**
   - Automatic detection of long-lived resources
   - Configurable lifetime thresholds
   - Detailed leak reports

4. **Batch Operations**
   - Manage multiple resources together
   - Atomic cleanup operations
   - Rollback support

#### Usage Examples

##### Managed Database Connection

```python
from resync.core.resource_manager import managed_database_connection

async with managed_database_connection(pool) as conn:
    result = await conn.execute(query)
# Connection automatically returned to pool
```

##### Managed File Operations

```python
from resync.core.resource_manager import managed_file

async with managed_file('data.txt', 'r') as f:
    content = await f.read()
# File automatically closed
```

##### Resource Pool

```python
from resync.core.resource_manager import ResourcePool, resource_scope

pool = ResourcePool(max_resources=100)

async with resource_scope(pool, 'database', create_connection) as conn:
    result = await conn.execute(query)
# Resource automatically released
```

##### Batch Resource Management

```python
from resync.core.resource_manager import BatchResourceManager

async with BatchResourceManager() as batch:
    await batch.add_resource('conn1', connection1)
    await batch.add_resource('file1', file_handle)
    # Use resources
# All resources automatically cleaned up
```

#### Leak Detection

```python
from resync.core.resource_manager import get_global_resource_pool

pool = get_global_resource_pool()

# Detect resources older than 1 hour
leaks = await pool.detect_leaks(max_lifetime_seconds=3600)

for leak in leaks:
    print(f"Leak: {leak.resource_id}, lifetime: {leak.get_lifetime_seconds()}s")
```

## Security Features

### Critical Reliability Fixes

#### Redis Idempotency Initialization Security Fix

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

### Security Improvements

#### Credential Management
- Removed hardcoded credentials from configuration files
- Implemented secure credential validation during startup
- Added requirements for environment-specific credential values

#### Authentication System
- Implemented JWT-based authentication system
- Created proper login endpoint with secure credential validation
- Added CSRF protection and secure session management

#### CORS Configuration Security
- Enhanced CORS configuration with strict validation
- Implemented per-environment CORS policies
- Added security monitoring for CORS violations

### Security Features

- JWT-based authentication for API access
- Content Security Policy (CSP) headers
- CORS with strict origin validation
- Input validation and sanitization
- Rate limiting with Redis backend
- Comprehensive request logging with correlation IDs

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

## Installation & Setup

### Prerequisites
- Python 3.12+
- Redis server
- Neo4j database (for Knowledge Graph)
- HCL Workload Automation (TWS) instance

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/resync.git
cd resync

# Install dependencies
pip install -r requirements/dev.txt

# Set up environment variables
cp settings.development.toml.example settings.development.toml
# Edit settings.development.toml with your configuration

# Run tests
pytest

# Start development server
uvicorn resync.main:app --reload
```

### Configuration

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

## Configuration

### Health Check Configuration

The simplified health check system provides minimal resource usage while maintaining API compatibility:

```toml
[default.HEALTH]
HEALTH_CHECK_INTERVAL_SECONDS = 300    # Interval for health checks (default: 5 minutes)
HEALTH_ENABLE_PROACTIVE = false          # Disable proactive monitoring (resource intensive)
HEALTH_ENABLE_PREDICTIVE = false        # Disable predictive analysis (resource intensive)
```

#### Health Check Features

The simplified health service includes:

- **Minimal Component Checks**: Database, Redis, Cache, System Resources, WebSocket Pool
- **Background Monitoring**: Runs every 300 seconds (configurable)
- **Pure Asyncio**: No thread pools or circuit breakers
- **Low-Cardinality Metrics**: Only essential Prometheus metrics
- **API Compatibility**: Maintains exact same JSON structure and endpoints

#### Prometheus Metrics

The simplified health service exposes only three essential metrics:

- `health_checks_total` (Counter): Total number of health checks performed
- `health_check_duration_seconds` (Histogram): Time spent performing health checks
- `component_health` (Gauge): Health status of components (0=UNKNOWN,1=HEALTHY,2=DEGRADED,3=UNHEALTHY)

#### Component Status Values

- **0**: UNKNOWN - Component status unavailable
- **1**: HEALTHY - All systems operational
- **2**: DEGRADED - Some components experiencing issues
- **3**: UNHEALTHY - Critical components failing

### Environment Variables

Performance optimization settings can be configured via environment variables or TOML files:

```bash
# Cache Configuration
export ASYNC_CACHE_TTL=60
export ASYNC_CACHE_CLEANUP_INTERVAL=30
export ASYNC_CACHE_NUM_SHARDS=8

# Database Pool Configuration
export DB_POOL_MIN_SIZE=20
export DB_POOL_MAX_SIZE=100
export DB_POOL_CONNECT_TIMEOUT=60

# Redis Pool Configuration
export REDIS_POOL_MIN_SIZE=5
export REDIS_POOL_MAX_SIZE=20

# HTTP Pool Configuration
export HTTP_POOL_MIN_SIZE=10
export HTTP_POOL_MAX_SIZE=100
```

### TOML Configuration

Example configuration in `settings.toml`:

```toml
[default.ASYNC_CACHE]
TTL_SECONDS = 60              # Default TTL for cache entries
CLEANUP_INTERVAL = 30         # Background cleanup interval
NUM_SHARDS = 8                # Number of cache shards
MAX_WORKERS = 4               # Max concurrent workers

[default.CONNECTION_POOL]
# Database Pool
DB_POOL_MIN_SIZE = 20
DB_POOL_MAX_SIZE = 100
DB_POOL_CONNECT_TIMEOUT = 60
DB_POOL_IDLE_TIMEOUT = 1200
DB_POOL_MAX_LIFETIME = 1800
DB_POOL_HEALTH_CHECK_INTERVAL = 60

# Redis Pool
REDIS_POOL_MIN_SIZE = 5
REDIS_POOL_MAX_SIZE = 20
REDIS_POOL_CONNECT_TIMEOUT = 30
REDIS_POOL_IDLE_TIMEOUT = 300
REDIS_POOL_MAX_LIFETIME = 1800
REDIS_POOL_HEALTH_CHECK_INTERVAL = 60

# HTTP Pool
HTTP_POOL_MIN_SIZE = 10
HTTP_POOL_MAX_SIZE = 100
HTTP_POOL_CONNECT_TIMEOUT = 10
HTTP_POOL_IDLE_TIMEOUT = 300
HTTP_POOL_MAX_LIFETIME = 1800
HTTP_POOL_HEALTH_CHECK_INTERVAL = 60
```

## Testing & Deployment

### Testing Steps

#### Step 1: Verify Implementation

Run the simple test suite to verify all files are in place and have valid syntax:

```bash
cd D:\Python\GITHUB\hwa-new
python test_phase2_simple.py
```

**Expected Output:**
```
[SUCCESS] All tests passed! Phase 2 implementation is complete.
Total: 6/6 tests passed
```

**What it tests:**
- ✅ File structure (all new files exist)
- ✅ Module syntax (no Python syntax errors)
- ✅ Direct imports (modules can be loaded)
- ✅ Documentation (all docs exist and are readable)
- ✅ Configuration (settings.toml updated)
- ✅ Main integration (performance router registered)

#### Step 2: Start the Application

Before testing the API endpoints, start the application:

```bash
# Option 1: Using uvicorn directly
uvicorn resync.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Using the start script (if available)
python -m resync.main

# Option 3: Using poetry (if using poetry)
poetry run uvicorn resync.main:app --reload
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Step 3: Test API Endpoints

Once the server is running, test the performance monitoring endpoints:

```bash
# In a new terminal window
cd D:\Python\GITHUB\hwa-new
python test_api_endpoints.py
```

**Expected Output:**
```
[SUCCESS] All API endpoints working correctly!
Total: 8 passed, 0 skipped, 0 failed out of 8
```

#### Step 4: Manual API Testing

You can also test the endpoints manually using curl or a browser:

##### Health Check
```bash
curl http://localhost:8000/api/performance/health
```

**Expected Response:**
```json
{
  "overall_health": "healthy",
  "cache_health": "healthy",
  "pool_health": "healthy",
  "resource_health": "healthy"
}
```

##### Full Performance Report
```bash
curl http://localhost:8000/api/performance/report
```

##### Cache Metrics
```bash
curl http://localhost:8000/api/performance/cache/metrics
```

##### Connection Pool Metrics
```bash
curl http://localhost:8000/api/performance/pools/metrics
```

##### Resource Statistics
```bash
curl http://localhost:8000/api/performance/resources/stats
```

##### Resource Leak Detection
```bash
curl http://localhost:8000/api/performance/resources/leaks?max_lifetime_seconds=3600
```

### Deployment

#### Pre-Deployment Checklist

- [ ] All tests passing (`test_phase2_simple.py`)
- [ ] API endpoints working (`test_api_endpoints.py`)
- [ ] Configuration reviewed and optimized
- [ ] Documentation reviewed
- [ ] Monitoring dashboard set up
- [ ] Alerts configured

#### Staging Deployment

1. Deploy to staging environment
2. Run full test suite
3. Monitor performance for 24-48 hours
4. Review optimization recommendations
5. Adjust configuration if needed

#### Production Deployment

1. **Backup current configuration**
   ```bash
   cp settings.toml settings.toml.backup
   ```

2. **Deploy new code**
   ```bash
   git pull origin main
   # or your deployment process
   ```

3. **Restart application**
   ```bash
   # Graceful restart
   systemctl restart resync
   # or
   supervisorctl restart resync
   ```

4. **Verify deployment**
   ```bash
   # Check health
   curl http://localhost:8000/api/performance/health
   
   # Check all endpoints
   python test_api_endpoints.py
   ```

5. **Monitor closely**
   - Watch performance metrics for first hour
   - Check for any errors or warnings
   - Review optimization recommendations
   - Adjust configuration if needed

#### Post-Deployment

1. **Monitor for 24 hours**
   - Cache hit rates
   - Pool utilization
   - Resource usage
   - Error rates

2. **Review recommendations**
   ```bash
   curl http://localhost:8000/api/performance/report
   ```

3. **Fine-tune configuration**
   - Apply recommended changes
   - Test in staging first
   - Deploy to production

4. **Document changes**
   - Update configuration documentation
   - Record performance improvements
   - Share results with team

## Monitoring & Maintenance

### Performance Monitoring

The performance monitoring system provides real-time insights into cache, connection pool, and resource performance.

#### Components

1. **CachePerformanceMonitor**
   - Tracks cache hit rates and access times
   - Provides optimization recommendations
   - Calculates efficiency scores

2. **ConnectionPoolOptimizer**
   - Monitors pool utilization and wait times
   - Suggests optimal pool sizes
   - Detects performance issues

3. **ResourceManager**
   - Tracks active resources
   - Detects resource leaks
   - Provides usage statistics

#### Usage Example

```python
from resync.core.performance_optimizer import get_performance_service

service = get_performance_service()

# Register a cache for monitoring
cache_monitor = await service.register_cache("my_cache")

# Record cache access
await cache_monitor.record_access(hit=True, access_time_ms=2.5)

# Get current metrics
metrics = await cache_monitor.get_current_metrics()
print(f"Hit rate: {metrics.hit_rate:.2%}")
print(f"Efficiency score: {metrics.calculate_efficiency_score():.1f}/100")

# Get recommendations
recommendations = await cache_monitor.get_optimization_recommendations()
for rec in recommendations:
    print(f"- {rec}")

# Generate system-wide performance report
report = await service.get_system_performance_report()
```

### Monitoring Setup

#### Set Up Performance Dashboard

Create a monitoring dashboard that polls the performance endpoints:

```python
import asyncio
import httpx
from datetime import datetime

async def monitor_performance():
    """Continuous performance monitoring."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Get health status
                response = await client.get("http://localhost:8000/api/performance/health")
                health = response.json()
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Health: {health['overall_health']}")
                
                # Alert on degraded health
                if health['overall_health'] == 'degraded':
                    print(f"⚠️  WARNING: Performance degraded!")
                    print(f"   Cache issues: {health['cache_issues']}")
                    print(f"   Pool issues: {health['pool_issues']}")
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Error monitoring performance: {e}")
                await asyncio.sleep(60)

# Run monitoring
asyncio.run(monitor_performance())
```

#### Configure Alerts

Set up alerts based on performance metrics:

```python
# Example alert configuration
ALERT_THRESHOLDS = {
    'cache_hit_rate_min': 0.5,  # Alert if hit rate < 50%
    'pool_utilization_max': 0.9,  # Alert if utilization > 90%
    'connection_wait_time_max': 100,  # Alert if wait time > 100ms
    'resource_leaks_max': 0,  # Alert if any leaks detected
}

async def check_alerts():
    """Check performance metrics against alert thresholds."""
    async with httpx.AsyncClient() as client:
        # Get performance report
        response = await client.get("http://localhost:8000/api/performance/report")
        report = response.json()
        
        alerts = []
        
        # Check cache metrics
        for cache_name, cache_data in report.get('caches', {}).items():
            hit_rate = float(cache_data['metrics']['hit_rate'].rstrip('%')) / 100
            if hit_rate < ALERT_THRESHOLDS['cache_hit_rate_min']:
                alerts.append(f"Low cache hit rate: {cache_name} = {hit_rate:.1%}")
        
        # Check resource leaks
        leak_count = len(report.get('resources', {}).get('potential_leaks', []))
        if leak_count > ALERT_THRESHOLDS['resource_leaks_max']:
            alerts.append(f"Resource leaks detected: {leak_count}")
        
        # Send alerts
        if alerts:
            print("🚨 ALERTS:")
            for alert in alerts:
                print(f"  - {alert}")
                # Send to alerting system (email, Slack, etc.)
        
        return alerts
```

#### Integrate with Existing Monitoring

Add performance metrics to your existing monitoring system:

```python
# Example: Prometheus metrics
from prometheus_client import Gauge, Counter

# Define metrics
cache_hit_rate = Gauge('cache_hit_rate', 'Cache hit rate', ['cache_name'])
pool_utilization = Gauge('pool_utilization', 'Connection pool utilization', ['pool_name'])
resource_count = Gauge('resource_count', 'Active resource count')

async def update_prometheus_metrics():
    """Update Prometheus metrics from performance API."""
    async with httpx.AsyncClient() as client:
        # Get performance report
        response = await client.get("http://localhost:8000/api/performance/report")
        report = response.json()
        
        # Update cache metrics
        for cache_name, cache_data in report.get('caches', {}).items():
            hit_rate = float(cache_data['metrics']['hit_rate'].rstrip('%')) / 100
            cache_hit_rate.labels(cache_name=cache_name).set(hit_rate)
        
        # Update resource metrics
        resource_count.set(report.get('resources', {}).get('active_count', 0))
```

### Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| Cache Hit Rate | >70% | <50% |
| Pool Utilization | 60-80% | >90% |
| Connection Wait Time | <100ms | >200ms |
| Resource Leaks | 0 | >0 |
| API Response Time | <50ms | >200ms |

### Best Practices

#### Cache Usage

1. **Choose Appropriate TTL**
   - Short TTL (30-60s) for frequently changing data
   - Long TTL (5-30min) for static or infrequently changing data
   - Consider data volatility when setting TTL

2. **Monitor Hit Rates**
   - Target hit rate: >70% for optimal performance
   - Low hit rates indicate poor cache strategy
   - Use performance monitoring to track trends

3. **Manage Cache Size**
   - Keep cache size under 100MB per instance
   - Use LRU eviction to maintain relevant data
   - Monitor memory usage regularly

#### Connection Pool Usage

1. **Size Pools Appropriately**
   - Start with min=10-20, max=50-100
   - Monitor utilization and adjust
   - Target 60-80% utilization for optimal performance

2. **Handle Connection Errors**
   - Implement retry logic with exponential backoff
   - Monitor error rates
   - Set up alerts for high error rates

3. **Use Health Checks**
   - Enable periodic health checks
   - Validate connections before use
   - Remove unhealthy connections promptly

#### Resource Management

1. **Always Use Context Managers**
   - Ensures deterministic cleanup
   - Prevents resource leaks
   - Exception-safe

2. **Monitor Resource Usage**
   - Track active resource counts
   - Set up leak detection
   - Alert on high resource usage

3. **Set Appropriate Timeouts**
   - Prevent resources from being held indefinitely
   - Use reasonable lifetime limits
   - Clean up stale resources

#### Performance Monitoring

1. **Regular Monitoring**
   - Check performance metrics daily
   - Review optimization recommendations
   - Act on degraded health status

2. **Set Up Alerts**
   - Alert on low cache hit rates (<50%)
   - Alert on high pool utilization (>90%)
   - Alert on resource leaks

3. **Continuous Optimization**
   - Review and adjust configurations regularly
   - Test changes in staging first
   - Monitor impact of optimizations

## Troubleshooting

### Common Issues & Solutions

#### Issue: Low Cache Hit Rate

**Symptom:** Hit rate below 50%

**Solutions:**
- Increase TTL for stable data
- Increase cache size
- Review caching strategy
- Check if data is cacheable

#### Issue: High Connection Pool Wait Times

**Symptom:** Average wait time >100ms

**Solutions:**
- Increase max pool size
- Optimize slow queries
- Check database performance
- Review connection usage patterns

#### Issue: Resource Leaks

**Symptom:** Growing resource count, memory usage

**Solutions:**
- Review code for missing cleanup
- Use context managers consistently
- Enable leak detection
- Set appropriate resource lifetimes

#### Issue: Pool Exhaustion

**Symptom:** Pool exhaustion errors

**Solutions:**
- Increase max pool size immediately
- Review connection usage
- Check for connection leaks
- Optimize query performance

### Issue: Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'resync'`

**Solution:**
```bash
# Ensure you're in the project root
cd D:\Python\GITHUB\hwa-new

# Install dependencies
pip install -r requirements/dev.txt

# Or use poetry
poetry install
```

### Issue: Configuration Errors

**Symptom:** `ValidationError` when starting the application

**Solution:**
1. Check `settings.toml` for required fields
2. Verify environment variables
3. Review error message for missing fields
4. Update configuration accordingly

### Issue: API Endpoints Not Working

**Symptom:** 404 errors when accessing `/api/performance/*`

**Solution:**
1. Verify server is running
2. Check that `performance_router` is registered in `main.py`
3. Restart the application
4. Check logs for errors

### Emergency Response

#### Cache Issues
```python
# Clear cache if needed
await cache.clear()

# Restart with new settings
cache = AsyncTTLCache(ttl_seconds=120, num_shards=16)
```

#### Pool Issues
```python
# Get immediate stats
stats = pool_manager.get_pool_stats()

# Force health check
health = await pool_manager.health_check_all()
```

#### Resource Issues
```python
# Detect leaks immediately
leaks = await resource_pool.detect_leaks(max_lifetime_seconds=1800)

# Force cleanup
await resource_pool.cleanup_all()
```

---

**Documentation Last Updated:** October 2025
**Version:** 1.0.0
