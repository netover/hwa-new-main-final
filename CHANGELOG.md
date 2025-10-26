# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2024-10-24

### Added
- **Security Improvements**: Enhanced validation for production environments with additional warnings
- **Secret Management**: Converted `neo4j_password`, `tws_password`, `llm_api_key` to `SecretStr` with exclusion from logging
- **CORS Security**: Default CORS settings now secure by default for development environment
- **Logging Redaction**: Added `SecretRedactor` filter to mask sensitive information in logs
- **Cache Configuration**: Exposed new cache knobs (`enable_cache_swr`, `cache_ttl_jitter_ratio`, `enable_cache_mutex`)
- **Rate Limiting**: Use separate Redis database (DB 1) for rate limiting to isolate from other data

### Changed
- **SemVer Support**: Updated version regex to accept pre-release and build metadata (e.g., 1.2.3-alpha+build.5)
- **Redis Configuration**: Unified connection pool settings with `redis_pool_min_size`/`redis_pool_max_size`, with fallback for deprecated settings
- **TWS SSL Verification**: Default `tws_verify` to `False` with warning in production (maintaining compatibility)
- **Neo4j Connections**: Allow `neo4j://` in production but emit suggestion to use `neo4j+s://`
- **Redis Connections**: Allow both `redis://` and `rediss://` schemes without requiring TLS
- **Cache Hierarchy**: Removed encryption feature from cache to simplify implementation

### Deprecated
- **Redis Settings**: `redis_min_connections` and `redis_max_connections` are deprecated in favor of `redis_pool_min_size` and `redis_pool_max_size`

### Fixed
- **Base Directory**: Improved `base_dir` resolution and validation
- **Settings Caching**: Added `@lru_cache` decorator to `get_settings()` and `clear_settings_cache()` for testing
- **CORS Validation**: Improved validation to warn when credentials enabled with wildcard origins

### Security
- **CORS Hardening**: Block wildcard origins in production environment
- **Credential Validation**: Strengthened validation for production environment requiring secrets
- **Sensitive Data**: Added redaction of sensitive data in logs (passwords, tokens, API keys)

## [1.3.0] - YYYY-MM-DD

### Added
- Initial version tracking