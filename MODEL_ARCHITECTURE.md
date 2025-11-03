# Resync Model Architecture

## Overview

This document describes the clean, domain-driven architecture for models in the Resync project. The architecture separates concerns between API representation, core domain logic, and health monitoring to eliminate circular dependencies and improve maintainability.

## Architecture Principles

### 1. Domain Separation
- **API Models**: Data Transfer Objects (DTOs) for HTTP requests/responses
- **Core Domain Models**: Business logic entities and enums
- **Health Domain Models**: Health monitoring and status tracking

### 2. Import Rules
- API models can import from core models (for conversion)
- Core models cannot import from API models
- Health models are part of core domain

### 3. Dependency Direction
```
API Layer → Core Domain (downward dependency)
         ↓
   Core Domain (business logic)
         ↓
   Infrastructure (databases, external APIs)
```

## Model Locations

### API Models (`resync/api/models/`)

#### Purpose
- HTTP request/response serialization
- API contract definitions
- Client-facing data structures

#### Structure
```
resync/api/models/
├── __init__.py      # Public API exports
├── base.py          # BaseModelWithTime, PaginationRequest/Response
├── auth.py          # LoginRequest, Token, UserRegistrationRequest
├── rag.py           # RAGFileCreate, RAGFileDetail, RAGFileMetaData
├── agents.py        # AgentConfig, AgentType
├── health.py        # SystemMetric (API representation)
└── responses.py     # HealthCheckResponse, ProblemDetail, etc.
```

#### Key Models
- `BaseModelWithTime`: Timestamp fields for all models
- `LoginRequest`, `Token`: Authentication DTOs
- `RAGFileCreate/Detail`: File upload operations
- `AgentConfig`: Agent management
- `SystemMetric`: Health metrics for API responses

### Core Domain Models (`resync/core/`)

#### Health Domain (`resync/core/health_models.py`)
- `SystemHealthStatus`: Overall system health (OK, WARNING, CRITICAL)
- `HealthStatus`: Component health states (HEALTHY, DEGRADED, UNHEALTHY)
- `ComponentType`: Types of system components
- `ComponentHealth`: Individual component status
- `HealthCheckResult`: Complete health check data

#### General Core Models
- Business logic models
- Domain entities
- Core enums and constants

## Import Relationships

### Allowed Imports
```python
# API models can import core models for conversion
from resync.core.health_models import SystemHealthStatus  # ✅ OK
from resync.api.models import SystemMetric               # ✅ OK in API layer

# Core models don't import API models
# from resync.api.models import ...  # ❌ NOT ALLOWED
```

### Circular Dependency Prevention
```python
# BEFORE (problematic)
# resync/core/health/health_check_service.py
from resync.api.models import SystemHealthStatus  # ❌ Wrong layer

# AFTER (correct)
# resync/core/health/health_check_service.py
from resync.core.health_models import SystemHealthStatus  # ✅ Correct layer
```

## API Layer Conversion Pattern

### Health Status Conversion
```python
# API endpoints convert between core and API models
from resync.core.health_models import SystemHealthStatus
from resync.api.models import SystemMetric

@app.get("/health")
async def get_health():
    # Get core domain health status
    core_status = await health_service.get_system_health()  # SystemHealthStatus

    # Convert to API representation
    api_metric = SystemMetric(
        metric_name="system_health",
        value=core_status.value,
        status=core_status  # Enum conversion
    )

    return api_metric
```

## Benefits

### 1. Clear Separation of Concerns
- API models: External interface contracts
- Core models: Business logic and state
- Health models: Monitoring domain

### 2. Eliminated Circular Dependencies
- No more API → Core → API cycles
- Clean dependency flow: API → Core

### 3. Improved Maintainability
- Changes to API don't affect core logic
- Core logic changes don't break API contracts
- Health monitoring isolated from API concerns

### 4. Better Testing
- API models can be tested independently
- Core models can be unit tested without API dependencies
- Health logic can be tested in isolation

## Migration Guide

### From Old Architecture
1. **Move enums to correct domains**
   - `SystemHealthStatus` → `resync.core.health_models`
   - Keep API-specific enums in API models

2. **Update imports**
   - Change `from resync.api.models import SystemHealthStatus`
   - To `from resync.core.health_models import SystemHealthStatus`

3. **Remove legacy files**
   - Delete `resync/api/models.py` (replaced by directory structure)

### Testing Migration
```bash
# Test core health functionality
python -c "from resync.core.health_models import SystemHealthStatus"

# Test API model imports
python -c "from resync.api.models import SystemMetric"

# Test health service integration
python -c "from resync.core.health.health_check_service import HealthCheckService"
```

## Future Extensions

### Adding New Domains
1. Create domain-specific model files in `resync/core/`
2. Define clear boundaries with existing domains
3. Update import rules documentation
4. Add conversion logic in API layer if needed

### API Versioning
- Use API models for version-specific representations
- Keep core models stable across API versions
- Convert between versions in API layer

## Conclusion

This architecture provides a solid foundation for scalable, maintainable model organization. The clear separation between API, core, and health domains eliminates circular dependencies while maintaining clean interfaces between layers.





























