# Resync API Documentation

## API Endpoints
### New Endpoints
```python
# POST /api/v2/validate-connection
# Implemented in endpoints.py
# Validates TWS connection parameters
# Request body:
# {
#   "auto_enable": true,
#   "tws_host": "string",
#   "tws_port": 31111,
#   "tws_user": "string",
#   "tws_password": "string"
# }
```

### Health Endpoints
```python
# /api/health
# Added auto_enable parameter for health checks
# Example: GET /api/health?auto_enable=true

# /api/health/tws
# Added auto_enable parameter for TWS health checks
# Example: GET /api/health/tws?auto_enable=true
```

## Core Components
### TWS Tools
#### TWSStatusTool
```python
async def get_tws_status() -> str:
    # Returns comprehensive TWS status
    # Includes connection validation
```

#### TWSTroubleshootingTool
```python
async def analyze_failures() -> str:
    # Analyzes failed jobs and down workstations
    # Includes validation logic
```

## Usage Examples
### Connection Validation
```python
import httpx

async def validate_connection():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v2/validate-connection",
            json={"auto_enable": True}
        )
        return response.json()
```

### Health Check with auto_enable
```python
import httpx

async def check_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/health",
            params={"auto_enable": True}
        )
        return response.json()
```

## Integration Guide
### Health Check Configuration
```bash
# Enable auto-connection validation
export HEALTH_AUTO_VALIDATE=true
```

## Security Testing
### Sensitive Endpoints
```python
# /api/sensitive
# Added validation for connection parameters
```

## Monitoring
### Connection Metrics
```python
# Prometheus metrics for connection validation
tws_connection_validations_total
connection_validation_success_total
connection_validation_failure_total
health_check_with_auto_enable_total
```

## Troubleshooting
### Connection Issues
1. **Validation Failures**: Check logs for validation errors
2. **Auto-Enable Problems**: Verify HEALTH_AUTO_VALIDATE environment variable


