# Security Migration Guide

## Overview

This guide provides instructions for migrating from the previous security implementation to the enhanced security features in Resync.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Migration Steps](#migration-steps)
3. [Code Changes](#code-changes)
4. [Testing](#testing)
5. [Deployment](#deployment)
6. [Rollback Procedure](#rollback-procedure)

## Prerequisites

Before migrating, ensure you have:

1. **Backup**: Complete backup of your current codebase and database
2. **Dependencies**: Install required security packages:
   ```bash
   pip install passlib bcrypt
   ```
3. **Environment**: Access to development, staging, and production environments
4. **Documentation**: Review the enhanced security documentation

## Migration Steps

### Step 1: Update Dependencies

Install the required security packages:

```bash
pip install passlib bcrypt
```

For production environments, ensure these packages are included in your requirements:

```txt
passlib>=1.7.4
bcrypt>=3.2.0
```

### Step 2: Update Import Statements

Replace old import statements with the new fixed module:

```python
# Before
from resync.api.validation.enhanced_security import EnhancedSecurityValidator

# After
from resync.api.validation.enhanced_security_fixed import EnhancedSecurityValidator
```

### Step 3: Update Authentication Models

Update your authentication models to include new security fields:

```python
# Before
class LoginRequest(BaseModel):
    username: str
    password: str

# After
class LoginRequest(BaseModel):
    username: str
    password: str
    # Security fields
    captcha_token: Optional[str] = None
    client_fingerprint: Optional[str] = None
    session_token: Optional[str] = None
```

### Step 4: Update Password Handling

Replace simple password comparisons with secure verification:

```python
# Before
if password == stored_password:
    # Authentication successful

# After
from resync.api.validation.enhanced_security_fixed import EnhancedSecurityValidator
validator = EnhancedSecurityValidator()
if await validator.verify_password(password, stored_hash):
    # Authentication successful
```

### Step 5: Update Configuration

Update your security configuration to use the new middleware:

```python
# In your main application file
from resync.config.enhanced_security import configure_enhanced_security

app = FastAPI()
configure_enhanced_security(app)
```

## Code Changes

### Authentication Endpoints

Update your authentication endpoints to use the new security features:

```python
from fastapi import Depends, HTTPException
from resync.api.validation.enhanced_security_fixed import (
    EnhancedSecurityValidator, 
    get_security_validator
)

@app.post("/login")
async def login(
    request: LoginRequest,
    validator: EnhancedSecurityValidator = Depends(get_security_validator)
):
    # Validate credentials with enhanced security
    username_result = await validator.validate_input_security(
        request.username, SecurityLevel.MEDIUM
    )
    
    if not username_result.is_valid:
        raise HTTPException(status_code=400, detail="Invalid username")
    
    # Use secure password verification
    if not await validator.verify_password(request.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate secure session
    session_id = await validator.generate_session_id()
    csrf_token = await validator.generate_csrf_token()
    
    return {
        "session_id": session_id,
        "csrf_token": csrf_token
    }
```

### Password Management

Update password management functions:

```python
@app.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    validator: EnhancedSecurityValidator = Depends(get_security_validator)
):
    # Validate current password
    if not await validator.verify_password(request.current_password, stored_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Validate new password strength
    password_result = await validator.validate_password_strength(
        request.new_password, SecurityLevel.HIGH
    )
    
    if not password_result.is_valid:
        raise HTTPException(status_code=400, detail=password_result.error_message)
    
    # Hash new password
    new_hash = await validator.hash_password(request.new_password)
    
    # Update in database (implementation dependent)
    # update_user_password(user_id, new_hash)
    
    return {"message": "Password changed successfully"}
```

## Testing

### Unit Tests

Run the enhanced security unit tests:

```bash
pytest tests/test_enhanced_security.py -v
```

### Integration Tests

Test the updated authentication flow:

```python
def test_secure_login():
    # Test with valid credentials
    response = client.post("/login", json={
        "username": "testuser",
        "password": "SecurePass123!",
        "captcha_token": "captcha123"
    })
    assert response.status_code == 200
    assert "session_id" in response.json()
    assert "csrf_token" in response.json()

def test_password_change():
    # Test password change with validation
    response = client.post("/change-password", json={
        "current_password": "OldPass123!",
        "new_password": "NewSecurePass456@",
        "confirm_password": "NewSecurePass456@"
    })
    assert response.status_code == 200
```

### Security Testing

Perform security-focused tests:

1. **Password Strength Testing**: Verify password validation rules
2. **Injection Testing**: Test for SQL/XSS injection vulnerabilities
3. **Brute Force Testing**: Verify rate limiting effectiveness
4. **Session Testing**: Validate session management security

## Deployment

### Staging Environment

1. Deploy to staging environment first
2. Run comprehensive tests
3. Monitor for any issues
4. Validate security headers are present

### Production Deployment

1. Schedule deployment during low-traffic period
2. Deploy with rollback capability
3. Monitor application logs closely
4. Verify security features are working correctly

### Environment Variables

Update environment variables if needed:

```env
# Enable production security features
SECURITY_LEVEL=HIGH
ENABLE_HSTS=true
ENABLE_CSP=true
```

## Rollback Procedure

If issues are encountered, follow this rollback procedure:

### Step 1: Immediate Rollback

1. Revert to previous code version
2. Restore database backup if needed
3. Restart application services

### Step 2: Issue Analysis

1. Check application logs for errors
2. Review security event logs
3. Identify root cause of issue

### Step 3: Fix and Retest

1. Apply necessary fixes
2. Test in staging environment
3. Validate security functionality
4. Redeploy with fixes

## Common Issues and Solutions

### Issue 1: Missing passlib Dependency

**Symptom**: Password verification fails with warning messages

**Solution**: Install passlib and bcrypt:
```bash
pip install passlib bcrypt
```

### Issue 2: Import Errors

**Symptom**: ModuleNotFoundError for enhanced_security_fixed

**Solution**: Verify the module was created correctly and is in the correct location

### Issue 3: Authentication Failures

**Symptom**: Users unable to log in after migration

**Solution**: 
1. Check password hashing implementation
2. Verify database password storage format
3. Ensure backward compatibility for existing hashes

## Performance Considerations

### Memory Usage

The enhanced security implementation may use slightly more memory due to:

- Additional validation objects
- Security context storage
- Enhanced logging data

### CPU Usage

Password hashing with bcrypt is CPU-intensive. Consider:

- Caching frequently accessed hashes
- Implementing rate limiting
- Monitoring CPU usage in production

## Monitoring and Logging

### Security Events

Monitor these security events:

- Failed authentication attempts
- Password change requests
- Security validation failures
- Rate limiting triggers

### Log Analysis

Set up log analysis for:

- Suspicious activity patterns
- Brute force attack attempts
- Validation failure trends
- Performance bottlenecks

## Support

For migration support, contact:

- **Security Team**: security@resync.example.com
- **Development Team**: dev@resync.example.com
- **Documentation**: Refer to enhanced_security.md

## Version Compatibility

This migration guide applies to:

- **Version**: Resync 2.0+
- **Security Module**: enhanced_security_fixed
- **Compatibility**: Backward compatible with 1.x authentication systems

## Changelog

### v1.0 (Initial Release)
- Basic migration guide
- Core security updates
- Authentication model changes

### v1.1 (Latest)
- Added rollback procedures
- Enhanced testing guidelines
- Performance considerations
- Common issues and solutions



