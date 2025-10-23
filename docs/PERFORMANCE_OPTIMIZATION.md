# Phase 2: Performance Optimization Implementation Guide

## Overview

This document describes the Phase 2 performance optimizations implemented in the Resync application. These optimizations focus on enhancing speed, efficiency, and responsiveness through improved memory management, connection pooling, and resource management.

## Table of Contents

1. [AsyncTTLCache Memory Management](#asyncttlcache-memory-management)
2. [Connection Pool Optimization](#connection-pool-optimization)
3. [Resource Management](#resource-management)
4. [Performance Monitoring](#performance-monitoring)
5. [API Endpoints](#api-endpoints)
6. [Configuration](#configuration)
7. [Best Practices](#best-practices)

---

## AsyncTTLCache Memory Management

### Overview

The `AsyncTTLCache` provides asynchronous, thread-safe caching with Time-To-Live (TTL) support and advanced memory management features.

### Key Features

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

### Configuration

```toml
[default.ASYNC_CACHE]
TTL_SECONDS = 60              # Default TTL for cache entries
CLEANUP_INTERVAL = 30         # Background cleanup interval
NUM_SHARDS = 8                # Number of cache shards
MAX_WORKERS = 4               # Max concurrent workers
```

### Usage Example

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

### Memory Management

The cache implements two-level memory bounds checking:

1. **Item Count Bounds**: Maximum 100,000 entries per cache instance
2. **Memory Usage Bounds**: Maximum 100MB per cache instance

When bounds are exceeded, the cache automatically evicts the least recently used entries.

### Performance Metrics

The cache tracks the following metrics:

- **Hit Rate**: Percentage of cache hits vs. total requests
- **Miss Rate**: Percentage of cache misses vs. total requests
- **Eviction Rate**: Percentage of evictions vs. total sets
- **Average Access Time**: Average time to access cache entries
- **Memory Usage**: Estimated memory consumption in MB

---

## Connection Pool Optimization

### Overview

Connection pools are optimized for database, Redis, and HTTP connections with automatic monitoring and tuning capabilities.

### Key Features

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

### Configuration

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

### Usage Example

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

### Pool Metrics

Each connection pool tracks:

- **Active Connections**: Currently in-use connections
- **Idle Connections**: Available connections in the pool
- **Waiting Requests**: Requests waiting for a connection
- **Average Wait Time**: Average time to acquire a connection
- **Connection Errors**: Number of connection failures
- **Pool Exhaustions**: Times the pool ran out of connections

### Optimization Recommendations

The system provides automatic recommendations based on metrics:

- **High Utilization (>90%)**: Increase max pool size
- **Low Utilization (<20%)**: Decrease min pool size
- **High Wait Times (>100ms)**: Increase pool size or optimize queries
- **High Error Rate (>5%)**: Check database health
- **Pool Exhaustions**: Increase max pool size immediately

---

## Resource Management

### Overview

The resource management system provides deterministic cleanup and leak detection for all system resources.

### Key Features

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

### Usage Examples

#### Managed Database Connection

```python
from resync.core.resource_manager import managed_database_connection

async with managed_database_connection(pool) as conn:
    result = await conn.execute(query)
# Connection automatically returned to pool
```

#### Managed File Operations

```python
from resync.core.resource_manager import managed_file

async with managed_file('data.txt', 'r') as f:
    content = await f.read()
# File automatically closed
```

#### Resource Pool

```python
from resync.core.resource_manager import ResourcePool, resource_scope

pool = ResourcePool(max_resources=100)

async with resource_scope(pool, 'database', create_connection) as conn:
    result = await conn.execute(query)
# Resource automatically released
```

#### Batch Resource Management

```python
from resync.core.resource_manager import BatchResourceManager

async with BatchResourceManager() as batch:
    await batch.add_resource('conn1', connection1)
    await batch.add_resource('file1', file_handle)
    # Use resources
# All resources automatically cleaned up
```

### Leak Detection

```python
from resync.core.resource_manager import get_global_resource_pool

pool = get_global_resource_pool()

# Detect resources older than 1 hour
leaks = await pool.detect_leaks(max_lifetime_seconds=3600)

for leak in leaks:
    print(f"Leak: {leak.resource_id}, lifetime: {leak.get_lifetime_seconds()}s")
```

---

## Performance Monitoring

### Overview

The performance monitoring system provides real-time insights into cache, connection pool, and resource performance.

### Components

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

### Usage Example

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

---

## API Endpoints

### Performance Report

**GET** `/api/performance/report`

Returns comprehensive system performance report including cache metrics, connection pool statistics, and resource usage.

**Response:**
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "caches": {
    "default": {
      "metrics": {
        "hit_rate": "85.5%",
        "efficiency_score": "82.3/100"
      },
      "recommendations": ["Cache performance is optimal."]
    }
  },
  "connection_pools": {...},
  "resources": {
    "active_count": 45,
    "potential_leaks": []
  },
  "overall_health": "healthy"
}
```

### Cache Metrics

**GET** `/api/performance/cache/metrics`

Returns detailed cache performance metrics.

### Cache Recommendations

**GET** `/api/performance/cache/recommendations`

Returns optimization recommendations for all caches.

### Pool Metrics

**GET** `/api/performance/pools/metrics`

Returns connection pool statistics and performance metrics.

### Pool Recommendations

**GET** `/api/performance/pools/recommendations`

Returns optimization recommendations for all connection pools.

### Resource Statistics

**GET** `/api/performance/resources/stats`

Returns resource usage statistics.

### Resource Leak Detection

**GET** `/api/performance/resources/leaks?max_lifetime_seconds=3600`

Detects and returns potential resource leaks.

### Performance Health

**GET** `/api/performance/health`

Returns overall performance health status.

---

## Configuration

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

See `settings.toml` for complete configuration options.

---

## Best Practices

### Cache Usage

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

### Connection Pool Usage

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

### Resource Management

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

### Performance Monitoring

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

---

## Troubleshooting

### Low Cache Hit Rate

**Symptoms:** Hit rate below 50%

**Solutions:**
- Increase TTL for stable data
- Increase cache size
- Review caching strategy
- Check if data is cacheable

### High Connection Pool Wait Times

**Symptoms:** Average wait time >100ms

**Solutions:**
- Increase max pool size
- Optimize slow queries
- Check database performance
- Review connection usage patterns

### Resource Leaks

**Symptoms:** Growing resource count, memory usage

**Solutions:**
- Review code for missing cleanup
- Use context managers consistently
- Enable leak detection
- Set appropriate resource lifetimes

### Pool Exhaustion

**Symptoms:** Pool exhaustion errors

**Solutions:**
- Increase max pool size immediately
- Review connection usage
- Check for connection leaks
- Optimize query performance

---

## Performance Metrics Reference

### Cache Efficiency Score

Score calculation (0-100):
- Hit rate: 60% weight
- Low eviction rate: 20% weight
- Memory efficiency: 20% weight

**Interpretation:**
- 80-100: Excellent
- 60-79: Good
- 40-59: Fair
- 0-39: Poor

### Pool Efficiency Score

Score calculation (0-100):
- Utilization (60-80% optimal): 40% weight
- Low wait time: 30% weight
- Low error rate: 30% weight

**Interpretation:**
- 80-100: Excellent
- 60-79: Good
- 40-59: Fair
- 0-39: Poor

---

## Additional Resources

- [AsyncTTLCache Implementation](../resync/core/async_cache.py)
- [Connection Pool Manager](../resync/core/pools/pool_manager.py)
- [Resource Manager](../resync/core/resource_manager.py)
- [Performance Optimizer](../resync/core/performance_optimizer.py)
- [Performance API](../resync/api/performance.py)

---

## Support

For questions or issues related to performance optimization:

1. Check the troubleshooting section
2. Review performance metrics via API endpoints
3. Consult the implementation code
4. Contact the development team

---

**Last Updated:** 2024-01-15
**Version:** 1.0.0
