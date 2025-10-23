# Phase 2 Performance Optimization - Quick Reference

## Quick Start

### 1. Cache Usage

```python
from resync.core.async_cache import AsyncTTLCache

# Create cache
cache = AsyncTTLCache(ttl_seconds=60)

# Basic operations
await cache.set("key", value)
data = await cache.get("key")
await cache.delete("key")
```

### 2. Connection Pool Usage

```python
from resync.core.pools.pool_manager import get_connection_pool_manager

# Get pool manager
pool_manager = await get_connection_pool_manager()

# Use database connection
db_pool = await pool_manager.get_pool("database")
async with db_pool.get_connection() as conn:
    result = await conn.execute(query)
```

### 3. Resource Management

```python
from resync.core.resource_manager import managed_database_connection

# Automatic cleanup
async with managed_database_connection(pool) as conn:
    result = await conn.execute(query)
```

### 4. Performance Monitoring

```python
from resync.core.performance_optimizer import get_performance_service

service = get_performance_service()
report = await service.get_system_performance_report()
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/performance/report` | Full performance report |
| `GET /api/performance/cache/metrics` | Cache metrics |
| `GET /api/performance/pools/metrics` | Pool metrics |
| `GET /api/performance/resources/leaks` | Detect leaks |
| `GET /api/performance/health` | Health status |

## Configuration Quick Reference

### Cache Settings (settings.toml)

```toml
[default.ASYNC_CACHE]
TTL_SECONDS = 60
CLEANUP_INTERVAL = 30
NUM_SHARDS = 8
```

### Database Pool Settings

```toml
[default.CONNECTION_POOL]
DB_POOL_MIN_SIZE = 20
DB_POOL_MAX_SIZE = 100
DB_POOL_CONNECT_TIMEOUT = 60
DB_POOL_IDLE_TIMEOUT = 1200
DB_POOL_MAX_LIFETIME = 1800
```

### Redis Pool Settings

```toml
REDIS_POOL_MIN_SIZE = 5
REDIS_POOL_MAX_SIZE = 20
REDIS_POOL_CONNECT_TIMEOUT = 30
REDIS_POOL_IDLE_TIMEOUT = 300
```

## Performance Targets

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Cache Hit Rate | >70% | Increase TTL or cache size |
| Pool Utilization | 60-80% | Adjust pool size |
| Connection Wait Time | <100ms | Increase pool size |
| Resource Leaks | 0 | Review cleanup code |

## Common Issues & Solutions

### Issue: Low Cache Hit Rate

**Solution:**
```python
# Increase TTL
await cache.set("key", value, ttl_seconds=300)

# Check recommendations
recommendations = await cache_monitor.get_optimization_recommendations()
```

### Issue: Pool Exhaustion

**Solution:**
```toml
# Increase max pool size
DB_POOL_MAX_SIZE = 150
```

### Issue: Resource Leaks

**Solution:**
```python
# Always use context managers
async with managed_resource(pool, 'type', factory) as resource:
    # Use resource
    pass
```

## Monitoring Commands

### Check Cache Performance

```bash
curl http://localhost:8000/api/performance/cache/metrics
```

### Check Pool Health

```bash
curl http://localhost:8000/api/performance/pools/metrics
```

### Detect Resource Leaks

```bash
curl http://localhost:8000/api/performance/resources/leaks?max_lifetime_seconds=3600
```

### Get Overall Health

```bash
curl http://localhost:8000/api/performance/health
```

## Best Practices Checklist

- [ ] Use context managers for all resources
- [ ] Monitor cache hit rates regularly
- [ ] Set appropriate TTLs based on data volatility
- [ ] Configure pool sizes based on load
- [ ] Enable health checks for all pools
- [ ] Set up alerts for performance degradation
- [ ] Review optimization recommendations weekly
- [ ] Test configuration changes in staging first

## Performance Optimization Workflow

1. **Monitor** - Check performance metrics
2. **Analyze** - Review recommendations
3. **Adjust** - Update configuration
4. **Test** - Verify improvements
5. **Deploy** - Roll out changes
6. **Repeat** - Continuous optimization

## Key Metrics to Watch

### Cache Metrics
- Hit Rate (target: >70%)
- Eviction Rate (target: <30%)
- Memory Usage (target: <100MB)
- Efficiency Score (target: >60)

### Pool Metrics
- Utilization (target: 60-80%)
- Wait Time (target: <100ms)
- Error Rate (target: <5%)
- Efficiency Score (target: >60)

### Resource Metrics
- Active Resources (monitor trends)
- Resource Leaks (target: 0)
- Utilization (target: <90%)

## Emergency Response

### Cache Issues
```python
# Clear cache if needed
await cache.clear()

# Restart with new settings
cache = AsyncTTLCache(ttl_seconds=120, num_shards=16)
```

### Pool Issues
```python
# Get immediate stats
stats = pool_manager.get_pool_stats()

# Force health check
health = await pool_manager.health_check_all()
```

### Resource Issues
```python
# Detect leaks immediately
leaks = await resource_pool.detect_leaks(max_lifetime_seconds=1800)

# Force cleanup
await resource_pool.cleanup_all()
```

## Additional Resources

- [Full Documentation](PERFORMANCE_OPTIMIZATION.md)
- [API Reference](../resync/api/performance.py)
- [Configuration Guide](../settings.toml)

---

**Quick Help:** For immediate assistance, check `/api/performance/health` endpoint
