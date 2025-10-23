# Dependency Management Consolidation Plan

## Current State

The project currently uses **multiple dependency management systems** simultaneously:

- **Poetry** (`pyproject.toml` + `poetry.lock`)
- **Requirements files** (`requirements.txt` + `requirements/` directory)

## Issues Identified

1. **Version conflicts**: Different version specifications between systems
2. **Maintenance overhead**: Need to update dependencies in multiple places
3. **CI/CD complexity**: Different installation commands for different environments

## Recommended Solution

### Phase 1: Choose Primary System (Completed ✅)
- **Decision**: Keep Poetry as primary system (has lock file for reproducible builds)
- **Keep**: `requirements/` directory for documentation and legacy compatibility

### Phase 2: Synchronize Versions (Completed ✅)
- Updated `pyproject.toml` with latest secure versions
- Synchronized critical dependencies:
  - `cryptography`: `^41.0.8` → `^42.0.0`
  - `openai`: `^1.3.5` → `^1.50.0`
  - `prometheus-client`: `^0.19.0` → `^0.20.0`

### Phase 3: Add Missing Dependencies (Completed ✅)
Added critical dependencies to `pyproject.toml`:
- `litellm = "^1.40.0"`
- `aiohttp = "^3.9.5"`
- `python-multipart = "^0.0.6"`
- `agno = "^0.1.0"`
- `jinja2 = "^3.1.4"`
- `uvicorn[standard] = "^0.24.0"`

## Future Recommendations

### Option A: Full Poetry Migration (Recommended)
```bash
# Remove legacy requirements.txt
rm requirements.txt

# Update CI to use only Poetry
# Update documentation to reference Poetry commands
```

### Option B: Keep Dual System for Compatibility
```bash
# Generate requirements.txt from Poetry
poetry export -f requirements.txt --output requirements.txt

# Keep requirements/ for documentation
# Use Poetry for development, requirements for production CI
```

## CI/CD Integration Strategy

### For Poetry-based CI:
```yaml
# .github/workflows/ci.yml
- name: Install dependencies
  run: |
    poetry install
    poetry check
```

### For Requirements-based CI (legacy):
```yaml
# .github/workflows/ci.yml
- name: Install dependencies
  run: |
    pip install -r requirements/dev.txt
```

## Migration Commands

```bash
# Update Poetry lock file
poetry update

# Export to requirements.txt if needed
poetry export -f requirements.txt --output requirements.txt

# Verify installation
poetry install --dry-run
```

## Benefits of Consolidation

1. **Single source of truth** for dependency versions
2. **Reproducible builds** via poetry.lock
3. **Simplified maintenance** - update in one place
4. **Better security** - Poetry handles dependency resolution conflicts
5. **Enhanced tooling** - Poetry provides better development experience

## Next Steps

1. Update CI/CD pipelines to use Poetry
2. Update developer documentation
3. Remove deprecated `requirements.txt` file
4. Add Poetry to development setup guides
