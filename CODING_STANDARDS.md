# Resync Coding Standards

## General Principles

1. **Follow PEP 8**
   All Python code must adhere to PEP 8 style guide, with exceptions documented.

2. **Type Hints**
   Use type hints for all function parameters and return types.

3. **Module/Function Structure**
   ```python
   # Module-level imports
   # Type aliases
   # Constants
   # Functions
   # Classes
   ```

4. **Line Length**
   Max 79 characters (80 for comments). Use automatic formatters.

5. **Error Handling**
   - Always log exceptions with context
   - Use specific exception types
   - Avoid bare `except:` clauses

## Project-Specific Rules

1. **Agent Development**
   - New agents must implement `AgentBase` interface
   - Follow naming convention: ` VerbNounAgent` (e.g., `CheckStatusAgent`)
   - All agents must have a `health_check()` method

2. **API Endpoints**
   - New endpoints must include OpenAPI summary and description
   - Use Pydantic models for request validation
   - Include proper status codes and error responses

3. **Dependency Management**
   - All dependencies must be pinned with exact versions
   - Security-critical packages must follow semantic versioning

4. **Testing**
   - Unit tests must cover all public functions
   - Integration tests must cover all API endpoints
   - Maintain >80% test coverage

5. **Documentation**
   - All new features must include:
     - Updated README
     - API documentation
     - Validation plan updates

## Code Formatting

1. **Tools**
   - `black` for code formatting
   - `ruff` for linting
   - `mypy` for type checking

2. **Configuration**
   - `.ruffignore` for excluding files
   - `pyproject.toml` contains all formatting rules

## Naming Conventions

| Element         | Convention                  | Example                  |
|----------------|-----------------------------|--------------------------|
| Functions      | `verb_noun`                | `get_job_status()`      |
| Classes        | `UpperCamelCase`           | `AgentBase`             |
| Variables      | `lower_case_with_underscores` | `current_job_count`     |
| Constants      | `UPPER_CASE`               | `MAX_RETRIES = 5`       |
| Modules        | `lower_case`               | `audit_lock.py`         |

## Error Handling Standards

1. **HTTP Status Codes**
   - 400 Bad Request
   - 401 Unauthorized
   - 403 Forbidden
   - 404 Not Found
   - 500 Internal Server Error
   - 503 Service Unavailable

2. **Error Messages**
   - Include context in error messages
   - Never expose sensitive information
   - Use consistent error format:
     ```json
     {
       "error": "BRIEF_DESCRIPTION",
       "details": {
         "code": "ERROR_CODE",
         "context": { /* Additional info */ }
       }
     }
     ```

## Commit Messages

Follow conventional commits format:
```
type(scope): subject

body
```

Example:
`feat(api): Add new health check endpoint`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code restructuring
- `test`: Test additions/fixes
- `chore`: Miscellaneous changes
- `build`: Build system changes
- `ci`: CI/CD configurations
- `revert`: Revert changes

## Branch Naming Convention

`type/short-description`

Examples:
- `feat/api-endpoint-docs`
- `fix/audit-lock-issue`
- `docs/update-validation-plan`

## Review Process

1. All changes require at least one approver
2. Use GitHub's pull request review system
3. Follow the CODE_REVIEW_COMPREHENSIVE.md guidelines



