"""
Exception Hierarchy Usage Examples

This file provides practical examples of how to use the standardized exception hierarchy
in various scenarios throughout the application.
"""

from resync.core.exceptions import (
    BaseAppException,
    ValidationError,
    ResourceNotFoundError,
    IntegrationError,
    FileIngestionError,
    InternalError,
    DatabaseError,
    CacheError,
    TWSConnectionError,
    LLMError,
    WebSocketError,
    TimeoutError,
    CircuitBreakerError,
    ErrorCode,
    ErrorSeverity
)


# ============================================================================
# EXAMPLE 1: API Route Exception Handling
# ============================================================================

def example_api_route_exception_handling():
    """
    Example of proper exception handling in API routes.

    This pattern should be used in all API endpoints to ensure consistent
    error responses and proper error categorization.
    """

    from flask import request, jsonify

    def upload_file_endpoint():
        """Example file upload endpoint with proper exception handling."""

        # Validate input
        if 'file' not in request.files:
            raise ValidationError(
                message="No file provided in request",
                details={"missing_field": "file"}
            )

        file = request.files['file']

        try:
            # Process the file
            result = process_uploaded_file(file)

            return jsonify({
                "status": "success",
                "result": result
            }), 200

        except FileIngestionError:
            # Re-raise file ingestion errors as-is (already properly categorized)
            raise

        except IntegrationError as e:
            # Re-raise integration errors as-is
            raise

        except ValidationError:
            # Re-raise validation errors as-is
            raise

        except Exception as e:
            # Wrap unexpected errors in InternalError with context
            raise InternalError(
                message=f"File upload failed: {str(e)}",
                details={
                    "filename": getattr(file, 'filename', 'unknown'),
                    "file_size": getattr(file, 'content_length', 0),
                    "original_error": str(e)
                },
                original_exception=e
            ) from e


# ============================================================================
# EXAMPLE 2: Service Layer Exception Handling
# ============================================================================

def example_service_layer_exceptions():
    """
    Example of exception handling in service layer classes.

    Services should catch external exceptions and convert them to appropriate
    domain-specific exceptions with proper context.
    """

    class UserService:
        """Example service class with proper exception handling."""

        async def get_user_by_id(self, user_id: str):
            """Retrieve user by ID with proper error handling."""

            try:
                # Database operation
                user = await self.db_client.query(
                    "SELECT * FROM users WHERE id = $1",
                    [user_id]
                )

                if not user:
                    raise ResourceNotFoundError(
                        message=f"User not found",
                        resource_type="user",
                        resource_id=user_id,
                        details={"user_id": user_id}
                    )

                return user

            except DatabaseError:
                # Re-raise database errors as-is
                raise

            except ResourceNotFoundError:
                # Re-raise not found errors as-is
                raise

            except Exception as e:
                # Wrap unexpected database errors
                raise DatabaseError(
                    message=f"Failed to retrieve user {user_id}",
                    query="SELECT * FROM users WHERE id = $1",
                    details={"user_id": user_id, "original_error": str(e)},
                    original_exception=e
                ) from e

        async def update_user_profile(self, user_id: str, profile_data: dict):
            """Update user profile with validation and error handling."""

            # Validate input data
            if not profile_data.get('email'):
                raise ValidationError(
                    message="Email is required",
                    details={"field": "email", "value": profile_data.get('email')}
                )

            try:
                # Update user in database
                await self.db_client.query(
                    "UPDATE users SET profile = $1 WHERE id = $2",
                    [profile_data, user_id]
                )

                # Invalidate user cache
                await self.cache_client.delete(f"user:{user_id}")

                return {"status": "updated"}

            except ValidationError:
                # Re-raise validation errors as-is
                raise

            except CacheError as e:
                # Log cache error but don't fail the operation
                logger.warning(f"Failed to invalidate user cache: {e}")
                # Continue with success response

            except DatabaseError:
                # Re-raise database errors as-is
                raise

            except Exception as e:
                # Wrap unexpected errors
                raise InternalError(
                    message=f"Failed to update user profile for {user_id}",
                    details={
                        "user_id": user_id,
                        "profile_fields": list(profile_data.keys()),
                        "original_error": str(e)
                    },
                    original_exception=e
                ) from e


# ============================================================================
# EXAMPLE 3: External Service Integration
# ============================================================================

def example_external_service_integration():
    """
    Example of handling exceptions when integrating with external services.

    This pattern should be used when calling external APIs, databases,
    or other services that may fail.
    """

    import httpx
    from resync.core.circuit_breaker import CircuitBreaker

    class TWSIntegrationService:
        """Example TWS integration with proper exception handling."""

        def __init__(self):
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60
            )

        async def get_job_status(self, job_id: str):
            """Get job status from TWS with proper error handling."""

            try:
                async with self.circuit_breaker:
                    response = await self.client.get(f"/jobs/{job_id}")
                    response.raise_for_status()

                    return response.json()

            except CircuitBreakerError as e:
                # Circuit breaker is open
                raise ServiceUnavailableError(
                    message=f"TWS service unavailable (circuit breaker open)",
                    service_name="TWS",
                    details={"job_id": job_id, "circuit_breaker_state": "open"},
                    original_exception=e
                ) from e

            except httpx.TimeoutException as e:
                # Request timeout
                raise TimeoutError(
                    message=f"TWS request timeout for job {job_id}",
                    timeout_seconds=30.0,
                    details={"job_id": job_id, "service": "TWS"},
                    original_exception=e
                ) from e

            except httpx.ConnectError as e:
                # Connection error
                raise TWSConnectionError(
                    message=f"Failed to connect to TWS for job {job_id}",
                    details={"job_id": job_id, "service": "TWS"},
                    original_exception=e
                ) from e

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # Job not found
                    raise ResourceNotFoundError(
                        message=f"Job {job_id} not found in TWS",
                        resource_type="job",
                        resource_id=job_id,
                        details={"service": "TWS", "status_code": e.response.status_code},
                        original_exception=e
                    ) from e

                elif e.response.status_code >= 500:
                    # Server error
                    raise IntegrationError(
                        message=f"TWS server error for job {job_id}",
                        service_name="TWS",
                        details={
                            "job_id": job_id,
                            "status_code": e.response.status_code,
                            "response_body": e.response.text[:500]  # Limit size
                        },
                        original_exception=e
                    ) from e

                else:
                    # Client error
                    raise IntegrationError(
                        message=f"TWS client error for job {job_id}",
                        service_name="TWS",
                        details={
                            "job_id": job_id,
                            "status_code": e.response.status_code
                        },
                        original_exception=e
                    ) from e

            except Exception as e:
                # Unexpected error
                raise IntegrationError(
                    message=f"Unexpected error communicating with TWS for job {job_id}",
                    service_name="TWS",
                    details={"job_id": job_id, "original_error": str(e)},
                    original_exception=e
                ) from e


# ============================================================================
# EXAMPLE 4: WebSocket Exception Handling
# ============================================================================

def example_websocket_exception_handling():
    """
    Example of proper exception handling in WebSocket events.

    WebSocket events need special handling since they can't return
    HTTP error responses.
    """

    from flask_socketio import emit

    def example_websocket_handler():
        """Example WebSocket event handler with proper exception handling."""

        @socketio.on('subscribe_to_job')
        async def handle_subscribe_to_job(data):
            """Client subscribes to job updates via WebSocket."""

            job_id = data.get('job_id')
            if not job_id:
                emit('error', {
                    'message': 'Job ID is required',
                    'error_code': ErrorCode.VALIDATION_ERROR
                })
                return

            try:
                # Validate job exists and is accessible
                job = await job_service.get_job(job_id)

                # Join the job room for updates
                join_room(f"job:{job_id}")

                # Send current status
                emit('job_status', {
                    'job_id': job_id,
                    'status': job.status,
                    'message': 'Successfully subscribed to job updates'
                })

            except ResourceNotFoundError as e:
                # Job not found
                emit('error', {
                    'message': f'Job {job_id} not found',
                    'error_code': e.error_code,
                    'details': e.details
                })

            except ValidationError as e:
                # Invalid job ID or permissions
                emit('error', {
                    'message': e.message,
                    'error_code': e.error_code,
                    'details': e.details
                })

            except WebSocketError as e:
                # WebSocket-specific error
                emit('error', {
                    'message': 'WebSocket connection error',
                    'error_code': e.error_code,
                    'details': e.details
                })

            except Exception as e:
                # Unexpected error - wrap in InternalError
                internal_error = InternalError(
                    message=f"Failed to subscribe to job {job_id}: {str(e)}",
                    details={"job_id": job_id, "original_error": str(e)},
                    original_exception=e
                )

                emit('error', {
                    'message': 'Internal server error',
                    'error_code': internal_error.error_code,
                    'correlation_id': internal_error.correlation_id
                })


# ============================================================================
# EXAMPLE 5: Custom Exception Creation
# ============================================================================

def example_custom_exception_creation():
    """
    Example of creating custom exceptions that follow the hierarchy.

    When you need a specific exception type that's not covered by the
    existing hierarchy, create it by inheriting from BaseAppException.
    """

    class PaymentProcessingError(BaseAppException):
        """Custom exception for payment processing errors."""

        def __init__(
            self,
            message: str,
            payment_id: str = None,
            amount: float = None,
            currency: str = None,
            **kwargs
        ):
            details = kwargs.get('details', {})
            if payment_id:
                details['payment_id'] = payment_id
            if amount:
                details['amount'] = amount
            if currency:
                details['currency'] = currency

            super().__init__(
                message=message,
                error_code=ErrorCode.INTEGRATION_ERROR,  # Or create specific code
                status_code=502,  # Payment service error
                details=details,
                severity=ErrorSeverity.ERROR,
                **kwargs
            )

    class InsufficientFundsError(PaymentProcessingError):
        """Specific exception for insufficient funds."""

        def __init__(
            self,
            message: str = "Insufficient funds for payment",
            payment_id: str = None,
            required_amount: float = None,
            available_amount: float = None,
            **kwargs
        ):
            super().__init__(
                message=message,
                payment_id=payment_id,
                error_code=ErrorCode.BUSINESS_RULE_VIOLATION,
                status_code=422,  # Unprocessable entity
                severity=ErrorSeverity.WARNING,
                **kwargs
            )

            # Add specific details for insufficient funds
            if required_amount:
                self.details['required_amount'] = required_amount
            if available_amount:
                self.details['available_amount'] = available_amount

    # Usage example
    def process_payment(payment_id: str, amount: float):
        """Process a payment with proper error handling."""

        try:
            # Simulate payment processing
            if amount > 1000:  # Simulate insufficient funds
                raise InsufficientFundsError(
                    message=f"Insufficient funds for payment {payment_id}",
                    payment_id=payment_id,
                    required_amount=amount,
                    available_amount=500.00
                )

            return {"status": "completed", "payment_id": payment_id}

        except InsufficientFundsError:
            # Re-raise business rule violations as-is
            raise

        except PaymentProcessingError:
            # Re-raise payment errors as-is
            raise

        except Exception as e:
            # Wrap unexpected payment errors
            raise PaymentProcessingError(
                message=f"Payment processing failed for {payment_id}",
                payment_id=payment_id,
                amount=amount,
                details={"original_error": str(e)},
                original_exception=e
            ) from e


# ============================================================================
# EXAMPLE 6: Exception Context and Correlation IDs
# ============================================================================

def example_exception_context():
    """
    Example of using correlation IDs and context for debugging.

    This is crucial for distributed tracing and debugging in production.
    """

    import uuid
    from flask import request

    def api_endpoint_with_correlation():
        """API endpoint that includes correlation ID in all exceptions."""

        # Get or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        try:
            # Some operation that might fail
            result = perform_critical_operation()

            return jsonify({"result": result}), 200

        except ValidationError as e:
            # Add correlation ID if not present
            if not e.correlation_id:
                e.correlation_id = correlation_id
            raise

        except DatabaseError as e:
            # Add correlation ID and context
            if not e.correlation_id:
                e.correlation_id = correlation_id
            if 'operation_context' not in e.details:
                e.details['operation_context'] = 'critical_operation'
            raise

        except Exception as e:
            # Wrap with correlation ID and context
            raise InternalError(
                message=f"Critical operation failed: {str(e)}",
                details={
                    "operation": "critical_operation",
                    "correlation_id": correlation_id,
                    "original_error": str(e)
                },
                correlation_id=correlation_id,
                original_exception=e
            ) from e


# ============================================================================
# EXAMPLE 7: Batch Operations with Exception Handling
# ============================================================================

def example_batch_operations():
    """
    Example of handling exceptions in batch operations.

    This pattern is useful when processing multiple items where some
    may fail while others succeed.
    """

    async def process_multiple_files(file_ids: list[str]):
        """Process multiple files, collecting both successes and failures."""

        results = {
            "successful": [],
            "failed": [],
            "errors": []
        }

        for file_id in file_ids:
            try:
                # Process individual file
                result = await process_single_file(file_id)
                results["successful"].append({
                    "file_id": file_id,
                    "result": result
                })

            except FileIngestionError as e:
                # File processing error - add to failed list
                results["failed"].append({
                    "file_id": file_id,
                    "error": e.message,
                    "error_code": e.error_code,
                    "details": e.details
                })

            except ValidationError as e:
                # Validation error - add to failed list
                results["failed"].append({
                    "file_id": file_id,
                    "error": e.message,
                    "error_code": e.error_code,
                    "details": e.details
                })

            except Exception as e:
                # Unexpected error - wrap and add to errors
                internal_error = InternalError(
                    message=f"Unexpected error processing file {file_id}",
                    details={"file_id": file_id, "original_error": str(e)},
                    original_exception=e
                )

                results["errors"].append({
                    "file_id": file_id,
                    "error": internal_error.message,
                    "error_code": internal_error.error_code,
                    "correlation_id": internal_error.correlation_id
                })

        return results


# ============================================================================
# UTILITY FUNCTIONS FOR EXCEPTION HANDLING
# ============================================================================

def create_exception_with_context(
    exception_class,
    message: str,
    context: dict = None,
    original_exception: Exception = None,
    **kwargs
):
    """
    Utility function to create exceptions with consistent context.

    Args:
        exception_class: The exception class to instantiate
        message: Error message
        context: Additional context dictionary
        original_exception: Original exception for chaining
        **kwargs: Additional arguments for the exception

    Returns:
        Exception instance with proper context
    """

    details = kwargs.get('details', {}) or {}
    if context:
        details.update(context)

    return exception_class(
        message=message,
        details=details,
        original_exception=original_exception,
        **kwargs
    )


def handle_service_exceptions(operation_name: str):
    """
    Decorator for consistent exception handling in service methods.

    Args:
        operation_name: Name of the operation for context

    Returns:
        Decorated function with exception handling
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)

            except (ValidationError, ResourceNotFoundError, BusinessError):
                # Re-raise business logic errors as-is
                raise

            except Exception as e:
                # Wrap unexpected errors with context
                raise InternalError(
                    message=f"{operation_name} failed: {str(e)}",
                    details={
                        "operation": operation_name,
                        "original_error": str(e)
                    },
                    original_exception=e
                ) from e

        return wrapper
    return decorator


# Example usage of the decorator
class ExampleService:
    """Example service using the exception handling decorator."""

    @handle_service_exceptions("user_creation")
    async def create_user(self, user_data: dict):
        """Create user with consistent exception handling."""
        # Implementation here
        pass

    @handle_service_exceptions("data_export")
    async def export_data(self, format: str):
        """Export data with consistent exception handling."""
        # Implementation here
        pass


if __name__ == "__main__":
    # Example usage and testing
    print("Exception hierarchy examples loaded successfully!")
    print("See the function docstrings for detailed usage patterns.")