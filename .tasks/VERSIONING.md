# Resync Versioning Strategy

## Semantic Versioning (SemVer)

Resync follows Semantic Versioning (SemVer) for all releases. Version numbers follow the format:

```
MAJOR.MINOR.PATCH
```

### Versioning Rules

| Component | When to Increment | Description |
|----------|------------------|-------------|
| **MAJOR** | Breaking changes | API changes, database schema changes, major functionality changes |
| **MINOR** | New features | Backward-compatible additions or changes |
| **PATCH** | Bug fixes | Minor fixes, security patches, documentation updates |

### Release Process

1. **Development**: `main` branch with version `x.y.z-beta.x`
2. **Release Candidate**: Tagged as `vX.Y.Z-rc.x`
3. **Production Release**: Tagged as `vX.Y.Z`

### Version Tagging

- Git tags follow format: `vX.Y.Z`
- Docker images tagged with version number
- Release notes included in `CHANGELOG.md`

### Dependency Management

- Use `poetry` or `pip-tools` for pinned dependencies
- Minor version updates allowed for non-breaking changes
- Major version updates require explicit review

### Example Version Progression

```
1.0.0 → 1.0.1 (Patch: security fix)
1.0.1 → 1.1.0 (Minor: new health check endpoint)
1.1.0 → 2.0.0 (Major: API restructuring)
```

### Changelog Format

`CHANGELOG.md` follows standard format:

```markdown
# Resync Changelog

## Unreleased

### Added
- New feature description

### Fixed
- Bug fix description

## v1.0.0 - 2025-09-24

### Added
- Initial release with core functionality

### Fixed
- Initial bug fixes
```

### Version Compatibility

- Maintain backward compatibility for MINOR versions
- Deprecation policy: 2 minor versions
- Breaking changes only in MAJOR versions

### Verification

- CI pipeline enforces version consistency
- `lint:version` check ensures correct version format
- Release process requires version bump in `pyproject.toml`

## Versioning in Practice

### When to Bump

| Change Type | Version Part | Example |
|-------------|--------------|---------|
| Add new API endpoint | MINOR | 1.0.0 → 1.1.0 |
| Fix bug in existing feature | PATCH | 1.1.0 → 1.1.1 |
| Change API response format | MAJOR | 1.1.0 → 2.0.0 |
| Security update | PATCH (or MINOR) | 1.1.0 → 1.1.1 or 1.2.0 |

### Communication

- Version changes documented in release notes
- Breaking changes announced 1 major version in advance
- Deprecation timeline published in documentation

### Tools

- `bump2version` for version bumps
- `github-release` for creating releases
- CI pipeline automation for version checks

### Branching Strategy

| Branch | Versioning |
|--------|------------|
| `main` | Current stable version (vX.Y.Z) |
| `develop` | Next upcoming version (vX.Y.Z-beta) |
| `feature/*` | Feature development branches |
| `hotfix/*` | Critical bug fixes for current version |

## Version Compatibility Table

| Version | Release Date | Supported Until | Notes |
|---------|--------------|-----------------|-------|
| 0.1.0   | 2025-09-01  | 2025-12-01     | Beta release |
| 1.0.0   | 2025-09-24  | 2026-09-24     | First stable release |



