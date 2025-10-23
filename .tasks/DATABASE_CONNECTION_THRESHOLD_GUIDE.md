# Database Connection Threshold Alerting Guide

## Overview
This guide documents the implementation of configurable threshold-based alerting for database active connections that triggers `HealthStatus.DEGRADED` when active connections exceed a specified percentage of total pool capacity.

## Key Features

### 1. Configurable Threshold
- **New Configuration Parameter**: `database_connection_threshold_percent` in `HealthCheckConfig`
- **Default Value**: 90.0% (matches the original requirement)
- **Range**: 0.0 to 100.0 (configurable)
- **Environment Variable**: Can be configured via settings

### 2. Health Status Determination
- **HEALTHY**: When active connections are below the threshold
- **DEGRADED**: When active connections meet or exceed the threshold
- **UNHEALTHY**: When total connections are 0 or other critical issues occur

### 3. Rich Metadata
Each health check includes:
- `connection_usage_percent`: Current usage as percentage
- `threshold_percent`: Configured threshold value
- `active_connections`: Current active connections
- `total_connections`: Total pool capacity
- `idle_connections`: Available idle connections

### 4. Alert Generation
When threshold is breached, alerts include:
- Specific usage percentage
- Configured threshold value
- Clear threshold breach information

## Configuration Examples

### Basic Configuration
```python
from resync.core.health_models import HealthCheckConfig

# Use default 90% threshold
config = HealthCheckConfig()

# Custom threshold at 80%
config = HealthCheckConfig(database_connection_threshold_percent=80.0)

# Conservative threshold at 70%
config = HealthCheckConfig(database_connection_threshold_percent=70.0)
```

### Environment Configuration
```bash
# In settings file or environment
DATABASE_CONNECTION_THRESHOLD_PERCENT=85.0
```

## Usage Examples

### 1. Health Check Response
```json
{
  "name": "database",
  "component_type": "database",
  "status": "degraded",
  "message": "Database connection pool near capacity: 18/20 (90.0%, threshold: 90.0%)",
  "metadata": {
    "active_connections": 18,
    "idle_connections": 2,
    "total_connections": 20,
    "connection_usage_percent": 90.0,
    "threshold_percent": 90.0,
    "connection_errors": 0,
    "pool_hits": 100,
    "pool_misses": 5
  }
}
```

### 2. Alert Generation
```json
{
  "alerts": [
    "Database connection pool usage at 95.0% (threshold: 90.0%)"
  ]
}
```

## Monitoring and Alerting

### Threshold Breach Scenarios
| Active Connections | Total Connections | Usage % | Threshold % | Status   | Alert? |
|-------------------|-------------------|---------|-------------|----------|--------|
| 15                | 20                | 75.0%   | 90.0%       | HEALTHY  | No     |
| 18                | 20                | 90.0%   | 90.0%       | DEGRADED | Yes    |
| 19                | 20                | 95.0%   | 90.0%       | DEGRADED | Yes    |
| 12                | 20                | 60.0%   | 50.0%       | DEGRADED | Yes    |

### Integration with Health Monitoring
The threshold-based alerting integrates seamlessly with:
- Comprehensive health checks
- Real-time monitoring loops
- Health history tracking
- Recovery mechanisms
- Memory bounds monitoring

## Testing

### Manual Testing
Run the included manual test:
```bash
python test_database_threshold_manual.py
```

### Key Test Cases
1. **Below Threshold**: 75% usage with 90% threshold → HEALTHY
2. **At Threshold**: 90% usage with 90% threshold → DEGRADED
3. **Above Threshold**: 95% usage with 90% threshold → DEGRADED
4. **Custom Threshold**: 90% usage with 75% threshold → DEGRADED
5. **Edge Cases**: Zero connections, empty stats

## Implementation Details

### Modified Files
- `resync/core/health_models.py`: Added `database_connection_threshold_percent` configuration
- `resync/core/health_service.py`: Updated `_check_database_health()` and `_check_alerts()`
- `test_database_threshold_manual.py`: Comprehensive testing script

### Key Functions Modified
1. `_check_database_health()`: Now uses configurable threshold
2. `_check_connection_pools_health()`: Enhanced with threshold logic
3. `_check_alerts()`: Added specific threshold breach alerts

## Migration Guide

### From Fixed 90% Threshold
No migration needed - the change is backward compatible. The default threshold remains 90.0%.

### Customizing Threshold
Simply set the new configuration parameter:
```python
# Before (fixed)
status = HealthStatus.DEGRADED if active > total * 0.9

# After (configurable)
threshold = config.database_connection_threshold_percent
status = HealthStatus.DEGRADED if usage_percent >= threshold
```

## Best Practices

1. **Choose Appropriate Thresholds**:
   - Production: 85-95% (allows for spikes)
   - Development: 70-80% (early warning)
   - Testing: 50-60% (frequent triggering)

2. **Monitor Trends**:
   - Track usage patterns over time
   - Adjust thresholds based on real usage data
   - Consider peak vs average usage

3. **Alert Integration**:
   - Set up notifications for DEGRADED status
   - Monitor threshold breach frequency
   - Implement auto-scaling based on usage patterns

## Troubleshooting

### Common Issues
1. **Threshold Not Taking Effect**: Ensure configuration is properly loaded
2. **False Positives**: Check if total_connections includes reserved connections
3. **No Alerts**: Verify alert_enabled is set to True in HealthCheckConfig

### Debug Commands
```python
# Check current threshold
health_service = HealthCheckService()
print(f"Current threshold: {health_service.config.database_connection_threshold_percent}%")

# Verify health status
result = await health_service.perform_comprehensive_health_check()
print(f"Database status: {result.components['database'].status}")
print(f"Metadata: {result.components['database'].metadata}")
```

## Future Enhancements
- Dynamic threshold adjustment based on historical data
- Per-database pool threshold configuration
- Predictive alerting based on connection growth rate
- Integration with automated scaling systems