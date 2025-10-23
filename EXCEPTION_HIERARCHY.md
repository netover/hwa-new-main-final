# Standardized Exception Hierarchy Documentation

## Overview

This project implements a comprehensive, standardized exception hierarchy based on the `BaseAppException` class defined in `resync/core/exceptions.py`. This hierarchy provides consistent error handling, proper HTTP status codes, error categorization, and detailed context for debugging across the entire application.

## Architecture

### Base Exception Class

All custom exceptions inherit from `BaseAppException`, which provides:

- **Error Codes**: Standardized error codes using the `ErrorCode` enum
- **HTTP Status Codes**: Appropriate HTTP status codes for API responses
- **Correlation IDs**: For distributed tracing and debugging
- **Context Details**: Additional context information for debugging
- **Severity Levels**: Critical, Error, Warning, Info levels
- **Timestamps**: When the error occurred
- **Exception Chaining**: Preserves original exception information

### Exception Categories

#### 1. Client Errors (4xx) - Errors caused by client requests

- **ValidationError** (400): Invalid input data
- **AuthenticationError** (401): Authentication failures
- **AuthorizationError** (403): Permission denied
- **ResourceNotFoundError** (404): Resource not found
- **ResourceConflictError** (409): Resource conflicts
- **BusinessError** (422): Business rule violations
- **RateLimitError** (429): Rate limit exceeded

#### 2. Server Errors (5xx) - Internal server errors

- **InternalError** (500): Unexpected internal errors
- **IntegrationError** (502): External service communication errors
- **ServiceUnavailableError** (503): Service temporarily unavailable
- **CircuitBreakerError** (503): Circuit breaker is open
- **TimeoutError** (504): Operation timeout

#### 3. Domain-Specific Errors

- **DatabaseError**: Database interaction errors
- **CacheError**: Cache system errors
- **RedisError**: Redis-specific errors
- **AgentError**: AI agent errors
- **TWSConnectionError**: TWS API connection errors
- **ToolExecutionError**: Tool execution errors
- **KnowledgeGraphError**: Knowledge graph errors
- **AuditError**: Audit system errors
- **FileIngestionError**: File processing errors
- **LLMError**: Large Language Model errors
- **ParsingError**: Data parsing errors
- **NetworkError**: Network-related errors
- **WebSocketError**: WebSocket-specific errors
- **NotificationError**: Notification system errors
- **PerformanceError**: Performance-related errors
- **HealthCheckError**: Health check failures

## Usage Examples

### Basic Exception Raising

```python
from resync.core.exceptions import ValidationError, DatabaseError, InternalError

# Validation error with details
raise ValidationError(
    message="Invalid email format",
    details={"field": "email", "value": "invalid-email"}
)

# Database error with context
raise DatabaseError(
    message="Failed to retrieve user data",
    query="SELECT * FROM users WHERE id = ?",
    details={"user_id": 123}
)

# Internal error with original exception
try:
    risky_operation()
except SomeExternalException as e:
    raise InternalError(
        message="Operation failed",
        details={"operation": "risky_operation"},
        original_exception=e
    ) from e
```

### Exception Handling in API Routes

```python
from resync.core.exceptions import (
    ValidationError, ResourceNotFoundError,
    IntegrationError, InternalError
)

@api.route('/users/<user_id>', methods=['GET'])
async def get_user(user_id: str):
    try:
        user = await user_service.get_user(user_id)
        return jsonify(user), 200

    except ResourceNotFoundError:
        # Re-raise not found errors as-is
        raise
    except IntegrationError:
        # Re-raise integration errors as-is
        raise
    except ValidationError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors
        raise InternalError(
            message=f"Failed to get user {user_id}: {str(e)}",
            details={"user_id": user_id, "original_error": str(e)},
            original_exception=e
        ) from e
```

### Exception Handling in WebSocket Events

```python
from resync.core.exceptions import (
    WebSocketError, ResourceNotFoundError,
    IntegrationError, InternalError
)

@socketio.on('join_job')
def handle_join_job(data):
    job_id = data.get('job_id')
    if not job_id:
        emit('error', {'message': 'Job ID required'})
        return

    try:
        # Join job room and get current status
        join_room(job_id)
        job_status = await get_job_status(job_id)
        emit('job_status', job_status)

    except ResourceNotFoundError:
        raise
    except IntegrationError:
        raise
    except WebSocketError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to join job {job_id}: {str(e)}",
            details={"job_id": job_id, "original_error": str(e)},
            original_exception=e
        ) from e
```

### Exception Handling in Services

```python
from resync.core.exceptions import (
    TWSConnectionError, TimeoutError, CircuitBreakerError
)

class TWSService:
    async def get_job_status(self, job_id: str):
        try:
            response = await self.client.get(f"/jobs/{job_id}")
            return response.data

        except httpx.TimeoutException as e:
            raise TimeoutError(
                message=f"TWS request timeout for job {job_id}",
                timeout_seconds=30.0,
                details={"job_id": job_id, "service": "TWS"},
                original_exception=e
            ) from e

        except httpx.RequestError as e:
            raise TWSConnectionError(
                message=f"TWS connection error for job {job_id}",
                details={"job_id": job_id, "service": "TWS"},
                original_exception=e
            ) from e

        except CircuitBreakerError:
            raise  # Re-raise circuit breaker errors as-is
```

## Error Response Format

When exceptions are properly handled by the FastAPI/Flask error handlers, they return standardized JSON responses:

```json
{
    "message": "Error description",
    "error_code": "VALIDATION_ERROR",
    "status_code": 400,
    "details": {
        "field": "email",
        "value": "invalid-email"
    },
    "correlation_id": "123e4567-e89b-12d3-a456-426614174000",
    "severity": "warning",
    "timestamp": "2024-01-15T10:30:00.000Z"
}
```

## Best Practices

### 1. Use Specific Exception Types

Always use the most specific exception type available:

```python
# ❌ Generic approach
except Exception as e:
    raise Exception(f"Something went wrong: {e}")

# ✅ Specific approach
except ValidationError:
    raise  # Re-raise specific errors
except DatabaseError as e:
    raise DatabaseError(
        message=f"Database operation failed: {e}",
        original_exception=e
    ) from e
```

### 2. Preserve Exception Context

Always use `from e` when wrapping exceptions to preserve the exception chain:

```python
try:
    external_service_call()
except ExternalServiceException as e:
    raise InternalError(
        message="External service call failed",
        original_exception=e  # This preserves the chain
    ) from e
```

### 3. Provide Meaningful Details

Include relevant context in the `details` parameter:

```python
raise ValidationError(
    message="Invalid user input",
    details={
        "field": "email",
        "value": user_input,
        "expected_format": "user@domain.com"
    }
)
```

### 4. Use Appropriate Severity Levels

- **CRITICAL**: System inoperative, requires immediate action
- **ERROR**: Functionality compromised
- **WARNING**: Potential problem
- **INFO**: Informational message

### 5. Include Correlation IDs

Always pass correlation IDs for distributed tracing:

```python
raise DatabaseError(
    message="Query failed",
    correlation_id=request.correlation_id,
    details={"query": sql_query}
)
```

## Migration Guide

### From Generic Exception Handling

**Before:**
```python
try:
    result = some_operation()
    return jsonify({"result": result}), 200
except Exception as e:
    return jsonify({"error": str(e)}), 500
```

**After:**
```python
try:
    result = some_operation()
    return jsonify({"result": result}), 200
except ValidationError:
    raise  # Re-raise specific errors
except DatabaseError:
    raise  # Re-raise specific errors
except Exception as e:
    raise InternalError(
        message=f"Operation failed: {str(e)}",
        details={"operation": "some_operation"},
        original_exception=e
    ) from e
```

### From Custom Exceptions

If you have existing custom exceptions, migrate them to inherit from `BaseAppException`:

```python
# ❌ Old custom exception
class MyCustomError(Exception):
    pass

# ✅ New standardized exception
class MyCustomError(BaseAppException):
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            **kwargs
        )
```

## Testing Exception Handling

```python
import pytest
from resync.core.exceptions import ValidationError, DatabaseError

def test_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        raise ValidationError(
            message="Invalid input",
            details={"field": "email"}
        )

    assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    assert exc_info.value.status_code == 400
    assert exc_info.value.details["field"] == "email"

def test_exception_chaining():
    original_error = ValueError("Original error")

    with pytest.raises(DatabaseError) as exc_info:
        try:
            raise original_error
        except ValueError as e:
            raise DatabaseError(
                message="Database operation failed",
                original_exception=e
            ) from e

    assert exc_info.value.original_exception is original_error
```

## Integration with Logging

The exception hierarchy integrates with the structured logging system:

```python
import logging
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

try:
    risky_operation()
except BaseAppException as e:
    logger.error(
        "Operation failed",
        error_code=e.error_code,
        status_code=e.status_code,
        correlation_id=e.correlation_id,
        details=e.details,
        exc_info=True
    )
```

This documentation provides a comprehensive guide for using the standardized exception hierarchy effectively across the application.