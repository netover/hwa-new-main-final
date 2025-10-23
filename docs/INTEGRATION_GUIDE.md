# Resync Integration Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [API Integration](#api-integration)
4. [WebSocket Integration](#websocket-integration)
5. [File Processing](#file-processing)
6. [Monitoring](#monitoring)
7. [Deployment](#deployment)
8. [Troubleshooting](#troubleshooting)

## Configuration
### Environment Variables
```bash
# Application
APP_ENV=development
PROJECT_NAME=Resync
PROJECT_VERSION=0.1.0

# Database Configuration
DB_POOL_MIN_SIZE=20  # Updated in settings.toml
DB_POOL_MAX_SIZE=100  # Updated in settings.toml

# Caching Configuration
USE_NEW_CACHING_LAYER=true  # Updated in settings.toml

# TWS Configuration
TWS_HOST=your-tws-host
TWS_PORT=31116
TWS_USER=your-username
TWS_PASSWORD=your-password
TWS_ENGINE_NAME=tws-engine
TWS_ENGINE_OWNER=tws-owner
TWS_MOCK_MODE=false
TWS_CACHE_TTL=300
```

### Agent Configuration
```json
{
  "agents": [
    {
      "id": "tws-specialist",
      "name": "TWS Specialist",
      "role": "TWS Environment Expert",
      "goal": "Help with TWS troubleshooting and monitoring",
      "backstory": "Expert in TWS operations and job scheduling",
      "tools": ["tws_status_tool", "tws_troubleshooting_tool"],
      "model_name": "llama3:latest",
      "memory": true,
      "verbose": false
    }
  ]
}
```

## API Integration
### New Endpoints
```python
# POST /api/v2/validate-connection
# Implemented in endpoints_new.py
```

### Health Endpoint Parameters
```bash
# /api/health
# Added auto_enable parameter
```

## Monitoring
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

### Prometheus Integration
```yaml
# health_monitor.py
PROMETHEUS_EXPORTER=1
```

## Deployment
### Docker Compose
```yaml
services:
  resync:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MAX_DB_CONNECTIONS=20
      - USE_NEW_CACHING_LAYER=true
    volumes:
      - ./agents.json:/app/agents.json
      - ./logs:/app/logs
```

## Troubleshooting
### Common Issues
1. **Connection Errors**: Verify TWS credentials in `.env`
2. **WebSocket Issues**: Check browser console for errors
3. **File Upload Failures**: Verify RAG_DIRECTORY path
4. **High Memory Usage**: Adjust Redis eviction policy