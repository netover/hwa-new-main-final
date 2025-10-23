# Resync Troubleshooting Guide

## Table of Contents
1. [Common Issues and Solutions](#common-issues-and-solutions)
2. [Diagnostic Tools](#diagnostic-tools)
3. [Log Analysis](#log-analysis)
4. [Connection Problems](#connection-problems)
5. [Performance Issues](#performance-issues)
6. [Model-Related Problems](#model-related-problems)
7. [Deployment Issues](#deployment-issues)
8. [Security Alerts](#security-alerts)
9. [Monitoring Configuration](#monitoring-configuration)

## Common Issues and Solutions
| Issue | Symptoms | Solution |
|-------|---------|----------|
| TWS Connection Failure | HTTP 503 errors | Verify credentials in `.env` |
| Model Not Responding | Timeout errors | Check LLM endpoint connectivity |
| Dashboard Not Loading | 404 errors | Ensure `templates/index.html` exists |
| API Not Accessible | Connection refused | Verify Docker containers are running |
| High Memory Usage | System swap/memory warnings | Adjust Redis eviction policy |

## Log Analysis
### Log Structure
```
logs/
├── YYYYMMDD/
│   ├── app.log
│   ├── error.log
│   └── access.log
```

### Log Rotation Configuration
```ini
# config/log_rotator.ini
[log_rotator]
log_dir = logs
max_size = 10MB
backup_count = 14
```

To implement log rotation in your application:

```python
# In your application's logging configuration
import logging
from logging.handlers import RotatingFileHandler

def setup_rotating_logger():
    logger = logging.getLogger('resync_logger')
    logger.setLevel(logging.INFO)
    
    handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=14
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
```

### Log Rotation Script
```bash
# scripts/rotate_logs.py
import logging
from logging.handlers import RotatingFileHandler

def setup_rotating_logger():
    logger = logging.getLogger('resync_logger')
    logger.setLevel(logging.INFO)
    
    handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=14
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
```

## Monitoring Configuration
### Prometheus Exporter
```python
# health_monitor.py
PROMETHEUS_EXPORTER=1

# In main.py or your application startup
from prometheus_client import start_http_server
start_http_server(8000)  # or another available port
```

### Grafana Dashboard Integration
```json
// grafana_dashboard.json
{
  "title": "Resync Monitoring",
  "variables": [
    {
      "name": "host",
      "type": "query",
      "datasource": "Prometheus",
      "query": "instance"
    }
  ],
  "panels": [
    {
      "title": "TWS Connection Status",
      "targets": [
        {
          "expr": "tws_connection_status{host=\"$host\"}",
          "legendFormat": "{{host}}"
        }
      ]
    }
  ]
}
```

## Diagnostic Tools
- **Health Endpoints**:
  - Application: `GET /health/app`
  - TWS Connection: `GET /health/tws`
  - Model Service: Check LLM provider status

- **Metrics**:
  - Prometheus metrics: `GET /metrics`
  - Key metrics: `tws_status_requests_total`, `tws_workstations_total`

- **Logging**:
  - Application logs: `docker logs resync-worker`
  - TWS API logs: Enable debug logging in `settings.py`

## Connection Problems
### TWS Connection Issues
1. Verify `.env` credentials
2. Check network connectivity to TWS server
3. Test connectivity manually:
   ```bash
   telnet $TWS_HOST $TWS_PORT
   ```
4. Check firewall rules

### Model Service Connection
1. Verify `LLM_ENDPOINT` URL
2. Check if LLM service is running
3. Test API connectivity:
   ```bash
   curl -X GET "$LLM_ENDPOINT/ready"
   ```

## Performance Issues
### Slow Responses
1. Check Redis connection status
2. Monitor system metrics
3. Verify cache is functioning
4. Review slow query logs

### High CPU/Memory Usage
1. Check container resource limits
2. Monitor Prometheus metrics
3. Optimize model parameters
4. Consider increasing service scale:
   ```bash
   docker-compose scale worker=3
   ```

## Model-Related Problems
### Incorrect Responses
1. Verify knowledge graph entries
2. Check for outdated context
3. Review LLM provider logs
4. Use the IA Auditor to validate memories

### Model Timeout
1. Increase timeout in `resync/core/utils/llm.py`
2. Check network latency to LLM provider
3. Switch to a faster model

## Deployment Issues
### Container Failures
1. Check Docker logs: `docker logs <container_name>`
2. Verify image builds
3. Ensure port availability
4. Check storage permissions

### Configuration Errors
1. Validate `.env` file
2. Check for missing environment variables
3. Verify file paths in configuration

## Security Alerts
### Unauthorized Access
1. Implement JWT authentication
2. Review access logs
3. Rotate API keys

### Vulnerability Reports
1. Run `pip-audit`
2. Check dependency vulnerabilities
3. Review security audit reports

### Data Exposure
1. Ensure HTTPS is used in production
2. Review field masking in logs
3. Validate input sanitization