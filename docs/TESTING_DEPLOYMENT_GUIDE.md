# Phase 2 Performance Optimization - Testing & Deployment Guide

## Overview

This guide provides step-by-step instructions for testing and deploying the Phase 2 performance optimizations.

## Prerequisites

- Python 3.12+
- All dependencies installed (`pip install -r requirements/dev.txt` or `uv sync`)
- Proper configuration in `settings.toml` or environment variables

## Testing Steps

### Step 1: Verify Implementation

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

### Step 2: Start the Application

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

### Step 3: Test API Endpoints

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

### Step 4: Manual API Testing

You can also test the endpoints manually using curl or a browser:

#### Health Check
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

#### Full Performance Report
```bash
curl http://localhost:8000/api/performance/report
```

#### Cache Metrics
```bash
curl http://localhost:8000/api/performance/cache/metrics
```

#### Connection Pool Metrics
```bash
curl http://localhost:8000/api/performance/pools/metrics
```

#### Resource Statistics
```bash
curl http://localhost:8000/api/performance/resources/stats
```

#### Resource Leak Detection
```bash
curl http://localhost:8000/api/performance/resources/leaks?max_lifetime_seconds=3600
```

### Step 5: Integration Testing

Test the performance optimization features in your application code:

#### Test Cache Monitoring

```python
import asyncio
from resync.core.performance_optimizer import get_performance_service

async def test_cache_monitoring():
    service = get_performance_service()
    
    # Register a cache
    cache_monitor = await service.register_cache("test_cache")
    
    # Simulate some cache accesses
    for i in range(100):
        hit = i % 3 != 0  # 66% hit rate
        await cache_monitor.record_access(hit=hit, access_time_ms=2.5)
    
    # Get metrics
    metrics = await cache_monitor.get_current_metrics()
    print(f"Hit rate: {metrics.hit_rate:.2%}")
    print(f"Efficiency score: {metrics.calculate_efficiency_score():.1f}/100")
    
    # Get recommendations
    recommendations = await cache_monitor.get_optimization_recommendations()
    for rec in recommendations:
        print(f"- {rec}")

asyncio.run(test_cache_monitoring())
```

#### Test Resource Management

```python
import asyncio
from resync.core.resource_manager import ResourcePool, resource_scope

async def test_resource_management():
    pool = ResourcePool(max_resources=100)
    
    # Test resource acquisition and release
    async def create_mock_resource():
        return {"connection": "mock"}
    
    async with resource_scope(pool, 'database', create_mock_resource) as resource:
        print(f"Resource acquired: {resource}")
        # Use resource
    
    # Resource automatically released
    stats = pool.get_stats()
    print(f"Active resources: {stats['active_resources']}")

asyncio.run(test_resource_management())
```

#### Test Connection Pool Optimization

```python
import asyncio
from resync.core.pools.pool_manager import get_connection_pool_manager

async def test_pool_optimization():
    pool_manager = await get_connection_pool_manager()
    
    # Get performance report
    report = await pool_manager.get_performance_report()
    print("Pool Performance Report:")
    for pool_name, pool_data in report['pools'].items():
        print(f"\n{pool_name}:")
        print(f"  Utilization: {pool_data['utilization']}")
        print(f"  Efficiency: {pool_data['efficiency_score']}")
        print(f"  Recommendations:")
        for rec in pool_data['recommendations']:
            print(f"    - {rec}")

asyncio.run(test_pool_optimization())
```

## Monitoring Setup

### Step 1: Set Up Performance Dashboard

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

### Step 2: Configure Alerts

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

### Step 3: Integrate with Existing Monitoring

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

## Configuration Optimization

### Step 1: Review Current Configuration

Check your current settings in `settings.toml`:

```bash
# View current configuration
cat settings.toml | grep -A 20 "CONNECTION_POOL"
```

### Step 2: Apply Recommendations

Get optimization recommendations from the API:

```bash
curl http://localhost:8000/api/performance/pools/recommendations
curl http://localhost:8000/api/performance/cache/recommendations
```

### Step 3: Update Configuration

Based on recommendations, update `settings.toml`:

```toml
[default.CONNECTION_POOL]
# Example: Increase pool size based on recommendations
DB_POOL_MIN_SIZE = 30  # Increased from 20
DB_POOL_MAX_SIZE = 150  # Increased from 100

# Example: Adjust timeouts
DB_POOL_CONNECT_TIMEOUT = 30  # Reduced from 60
DB_POOL_IDLE_TIMEOUT = 600  # Reduced from 1200
```

### Step 4: Test Configuration Changes

After updating configuration:

1. Restart the application
2. Monitor performance metrics
3. Verify improvements
4. Adjust as needed

## Deployment

### Step 1: Pre-Deployment Checklist

- [ ] All tests passing (`test_phase2_simple.py`)
- [ ] API endpoints working (`test_api_endpoints.py`)
- [ ] Configuration reviewed and optimized
- [ ] Documentation reviewed
- [ ] Monitoring dashboard set up
- [ ] Alerts configured

### Step 2: Staging Deployment

1. Deploy to staging environment
2. Run full test suite
3. Monitor performance for 24-48 hours
4. Review optimization recommendations
5. Adjust configuration if needed

### Step 3: Production Deployment

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

### Step 4: Post-Deployment

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

## Troubleshooting

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

### Issue: Low Cache Hit Rate

**Symptom:** Hit rate < 50%

**Solution:**
1. Check recommendations: `curl http://localhost:8000/api/performance/cache/recommendations`
2. Increase TTL for stable data
3. Increase cache size
4. Review caching strategy

### Issue: High Pool Utilization

**Symptom:** Pool utilization > 90%

**Solution:**
1. Check recommendations: `curl http://localhost:8000/api/performance/pools/recommendations`
2. Increase max pool size
3. Optimize slow queries
4. Review connection usage patterns

### Issue: Resource Leaks

**Symptom:** Growing resource count

**Solution:**
1. Check for leaks: `curl http://localhost:8000/api/performance/resources/leaks`
2. Review code for missing cleanup
3. Use context managers consistently
4. Set appropriate resource lifetimes

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| Cache Hit Rate | >70% | <50% |
| Pool Utilization | 60-80% | >90% |
| Connection Wait Time | <100ms | >200ms |
| Resource Leaks | 0 | >0 |
| API Response Time | <50ms | >200ms |

## Support

For issues or questions:

1. Check this guide
2. Review [PERFORMANCE_OPTIMIZATION.md](../docs/PERFORMANCE_OPTIMIZATION.md)
3. Check [PERFORMANCE_QUICK_REFERENCE.md](../docs/PERFORMANCE_QUICK_REFERENCE.md)
4. Contact the development team

## Next Steps

After successful deployment:

1. **Week 1:** Monitor closely, adjust configuration
2. **Week 2:** Review performance trends, optimize further
3. **Month 1:** Analyze long-term patterns, plan improvements
4. **Ongoing:** Continuous monitoring and optimization

---

**Good luck with your deployment! 🚀**
