# Resync API Documentation Guide

## Introduction

This document provides a comprehensive guide to the Resync API, which powers the intelligent interface for HCL Workload Automation (TWS). The API follows RESTful principles and is built using FastAPI, providing automatic OpenAPI/Swagger documentation at `/docs`.

## Getting Started

### Base URL
All API endpoints are available under the base path `/`

### Authentication
[To be implemented - Currently in development]
- **Planned Authentication**: JWT Bearer tokens
- **Scope**: Will require valid token for all endpoints except health checks

### Content Types
- Request/Response Format: `application/json`

## Endpoints Reference

### 1. Dashboard
**GET /dashboard**
- **Description**: Serves the main dashboard HTML interface
- **Response**: HTML content of the dashboard
- **Example Request**:
  ```bash
  curl -X GET "http://localhost:8000/dashboard"
  ```
- **Notes**: Returns the raw HTML file for the dashboard. Requires static files to be properly configured.

### 2. Agents
**GET /agents**
- **Description**: Retrieves all configured agents with their settings
- **Response Model**:
  ```json
  [
    {
      "agent_id": "string",
      "type": "string",
      "status": "string",
      "config": {
        "parameters": {}
      }
    }
  ]
  ```
- **Example Request**:
  ```bash
  curl -X GET "http://localhost:8000/agents"
  ```
- **Notes**: Agents are core components that handle specific tasks within the system.

### 3. System Status
**GET /status**
- **Description**: Provides comprehensive TWS environment status
- **Response Model**:
  ```json
  {
    "workstations": List[WorkstationStatus],
    "jobs": List[JobStatus],
    "critical_jobs": List[CriticalJobStatus]
  }
  ```
- **Example Request**:
  ```bash
  curl -X GET "http://localhost:8000/status"
  ```
- **Error Responses**:
  - `503 Service Unavailable`: TWS connection issues

### 4. Health Checks
**GET /health/app**
- **Description**: Basic application health check
- **Response**:
  ```json
  {"status": "ok"}
  ```
- **Example Request**:
  ```bash
  curl -X GET "http://localhost:8000/health/app"
  ```

**GET /health/tws**
- **Description**: Checks TWS connection health
- **Response**:
  ```json
  {"status": "ok", "message": "Conexão com o TWS bem-sucedida."}
  ```
- **Error Responses**:
  - `503 Service Unavailable`: TWS connection failed

### 5. Metrics
**GET /metrics**
- **Description**: Exposes application metrics in Prometheus format
- **Response**: Plain text Prometheus metrics
- **Example Request**:
  ```bash
  curl -X GET "http://localhost:8000/metrics"
  ```
- **Notes**: Includes custom metrics for TWS status requests, workstations, and jobs.

## Error Handling

All endpoints return standard HTTP status codes:
- `200 OK`: Successful request
- `404 Not Found`: Resource not found
- `503 Service Unavailable`: TWS connection issues
- `500 Internal Server Error`: Unexpected server errors

Error responses generally follow this format:
```json
{
  "detail": "Specific error message"
}
```

## Best Practices

1. **Use Async Features**: All endpoints are async-ready for optimal performance
2. **Rate Limiting**: [To be implemented] - Plan for rate limiting in production
3. **Security**: [To be implemented] - Use HTTPS and authentication in production
4. **Caching**: Consider caching frequent status requests where appropriate

## Swagger UI

The interactive API documentation is available at `/docs`. This provides:
- Full endpoint descriptions
- Request/response examples
- Live testing capabilities
- Downloadable OpenAPI specification

## Contributing to the API

For developers looking to extend the API:
1. Create new endpoint files in `resync/api/`
2. Follow existing patterns for routing and dependency injection
3. Update this documentation with new endpoint details
4. Generate updated OpenAPI spec with `uvicorn --reload`



