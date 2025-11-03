"""
Example usage of enhanced security features in Resync application.
"""

from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

from resync.api.validation.enhanced_security import (
    EnhancedSecurityValidator,
    SecurityContext,
    SecurityLevel,
    get_security_validator,
    validate_email,
    validate_input,
    validate_password,
)


# Example models with enhanced security
class SecureUserRegistration(BaseModel):
    """User registration with enhanced security validation."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Username for the account"
    )

    email: str = Field(..., description="Email address for the account")

    password: str = Field(
        ..., min_length=12, description="Strong password for the account"
    )

    # Security fields
    captcha_token: str | None = Field(
        None, description="CAPTCHA token for bot protection"
    )

    terms_accepted: bool = Field(
        ..., description="Whether terms and conditions are accepted"
    )


class SecureLoginRequest(BaseModel):
    """Login request with enhanced security validation."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Username for authentication"
    )

    password: str = Field(..., min_length=8, description="Password for authentication")

    # Security fields
    captcha_token: str | None = Field(
        None, description="CAPTCHA token for bot protection"
    )

    client_fingerprint: str | None = Field(
        None, description="Client fingerprint for device recognition"
    )


# Example FastAPI application
app = FastAPI(title="Resync Enhanced Security Example")


@app.post("/register", response_model=dict)
async def register_user(  # type: ignore[no-untyped-def]
    request: SecureUserRegistration,
    security_validator: EnhancedSecurityValidator = Depends(get_security_validator),
):
    """
    Register a new user with enhanced security validation.

    Args:
        request: User registration request
        security_validator: Security validator dependency

    Returns:
        Registration result
    """
    # Validate username
    username_result = await security_validator.validate_input_security(
        request.username, SecurityLevel.HIGH
    )
    if not username_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid username: {username_result.error_message}",
        )

    # Validate email with enhanced security
    email_result = await validate_email(
        request.email, SecurityLevel.HIGH, security_validator
    )
    if not email_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email: {email_result.error_message}",
        )

    # Validate password strength
    password_result = await validate_password(
        request.password, SecurityLevel.HIGH, security_validator
    )
    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weak password: {password_result.error_message}",
        )

    # Check terms acceptance
    if not request.terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terms and conditions must be accepted",
        )

    # Log security event
    SecurityContext(
        user_id=None,  # Not yet assigned
        ip_address="192.168.1.100",  # Would come from request in real app
        threat_level=SecurityLevel.MEDIUM,
        metadata={
            "action": "user_registration",
            "username": username_result.sanitized_value,
            "email_domain": (
                email_result.sanitized_value.split("@")[1]
                if email_result.sanitized_value and "@" in email_result.sanitized_value
                else "unknown"
            ),
        },
    )

    # In a real application, you would:
    # 1. Hash the password
    # 2. Store user in database
    # 3. Send verification email
    # 4. Log the security event

    return {
        "message": "User registered successfully",
        "username": username_result.sanitized_value,
        "email": email_result.sanitized_value,
        "security_level": "high",
    }


@app.post("/login", response_model=dict)
async def login_user(  # type: ignore[no-untyped-def]
    request: SecureLoginRequest,
    security_validator: EnhancedSecurityValidator = Depends(get_security_validator),
):
    """
    Authenticate a user with enhanced security validation.

    Args:
        request: Login request
        security_validator: Security validator dependency

    Returns:
        Authentication result
    """
    # Validate username
    username_result = await security_validator.validate_input_security(
        request.username, SecurityLevel.MEDIUM
    )
    if not username_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid username: {username_result.error_message}",
        )

    # Validate password (don't sanitize passwords!)
    password_result = await security_validator.validate_password_strength(
        request.password, SecurityLevel.HIGH
    )
    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid password: {password_result.error_message}",
        )

    # In a real application, you would:
    # 1. Verify credentials against database
    # 2. Check rate limiting
    # 3. Generate secure tokens
    # 4. Log the security event

    # Generate CSRF token for session
    csrf_token = await security_validator.generate_csrf_token()

    # Create security context for this session
    security_context = SecurityContext(
        user_id=username_result.sanitized_value,
        ip_address="192.168.1.100",  # Would come from request in real app
        session_id=await security_validator.generate_session_id(),
        threat_level=SecurityLevel.LOW,
        metadata={
            "action": "user_login",
            "auth_method": "password",
            "client_fingerprint": request.client_fingerprint,
        },
    )

    # Store session context (would go to database/session store in real app)
    if security_context.session_id:
        security_validator.session_store.setdefault(
            security_context.session_id, security_context
        )

    return {
        "message": "Login successful",
        "user": username_result.sanitized_value,
        "session_id": security_context.session_id,
        "csrf_token": csrf_token,
        "security_level": "high",
    }


@app.post("/validate-input", response_model=dict)
async def validate_user_input(  # type: ignore[no-untyped-def]
    input_text: str,
    security_validator: EnhancedSecurityValidator = Depends(get_security_validator),
):
    """
    Validate user input with enhanced security checks.

    Args:
        input_text: Text to validate
        security_validator: Security validator dependency

    Returns:
        Validation result
    """
    # Validate input with high security level
    result = await validate_input(input_text, SecurityLevel.HIGH, security_validator)

    return {
        "is_valid": result.is_valid,
        "sanitized_value": result.sanitized_value,
        "error_message": result.error_message,
        "threat_detected": (
            result.threat_detected.value if result.threat_detected else None
        ),
        "security_context": result.security_context.dict(),
    }


@app.get("/security-status", response_model=dict)
async def get_security_status(  # type: ignore[no-untyped-def]
    request: Request,
    security_validator: EnhancedSecurityValidator = Depends(get_security_validator),
):
    """
    Get current security status and configuration.

    Args:
        request: HTTP request
        security_validator: Security validator dependency

    Returns:
        Security status information
    """
    # Check rate limiting
    rate_limit = await security_validator.rate_limit_check(
        request.client.host if request.client else "unknown"
    )

    # Generate security context
    security_context = SecurityContext(
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
        threat_level=SecurityLevel.LOW,
    )

    return {
        "rate_limit": rate_limit.dict(),
        "security_context": security_context.dict(),
        "active_sessions": len(security_validator.session_store),
        "security_level": "enhanced",
    }


# Example of using async context managers for security operations
async def example_secure_operation(user_id: str, operation: str) -> dict[str, str]:
    """
    Example of a secure operation using async context managers.

    Args:
        user_id: ID of the user performing the operation
        operation: Name of the operation being performed
    """
    # Create security context
    context = SecurityContext(
        user_id=user_id,
        ip_address="192.168.1.100",
        threat_level=SecurityLevel.MEDIUM,
        metadata={"operation": operation},
    )

    # Use security validator with context manager
    validator = EnhancedSecurityValidator()

    async with validator.security_context(context) as security_ctx:
        # Perform secure operation
        print(f"Performing secure operation: {operation}")
        print(f"Security context: {security_ctx}")

        # Log security event
        from resync.api.validation.enhanced_security import (
            SecurityEventLog,
            SecurityEventSeverity,
            SecurityEventType,
        )

        event = SecurityEventLog(
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            severity=SecurityEventSeverity.INFO,
            user_id=user_id,
            source_ip=security_ctx.ip_address,
            details={"operation": operation},
        )
        await validator.log_security_event(event)

        # Return result
        return {"status": "success", "operation": operation}


# Example usage
async def main() -> None:
    """Example usage of enhanced security features."""
    print("=== Enhanced Security Example ===")

    # Example 1: Password validation
    validator = EnhancedSecurityValidator()
    password_result = await validator.validate_password_strength(
        "SecurePass123!@", SecurityLevel.HIGH
    )
    print(f"Password validation: {password_result.is_valid}")
    print(f"Error message: {password_result.error_message}")

    # Example 2: Email validation
    email_result = await validator.validate_email_security(
        "user@example.com", SecurityLevel.HIGH
    )
    print(f"Email validation: {email_result.is_valid}")
    print(f"Sanitized email: {email_result.sanitized_value}")

    # Example 3: Input validation
    input_result = await validator.validate_input_security(
        "This is a test input", SecurityLevel.MEDIUM
    )
    print(f"Input validation: {input_result.is_valid}")
    print(f"Sanitized input: {input_result.sanitized_value}")

    # Example 4: CSRF token generation
    csrf_token = await validator.generate_csrf_token()
    print(f"Generated CSRF token: {csrf_token[:20]}...")

    # Example 5: Password hashing
    password = "MySecurePassword123!"
    hashed = await validator.hash_password(password)
    is_valid = await validator.verify_password(password, hashed)
    print(f"Password hashing verification: {is_valid}")

    # Example 6: Secure operation with context manager
    result = await example_secure_operation("test_user", "data_access")
    print(f"Secure operation result: {result}")

    return


if __name__ == "__main__":
    # Run example
    asyncio.run(main())




