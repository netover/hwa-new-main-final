# Resync Project File Structure Documentation

This document provides an overview of the Resync project's file structure and explains the purpose of each major file and directory.

## Project Overview

Resync is an AI-powered interface for HCL Workload Automation (HWA), formerly known as IBM Tivoli Workload Scheduler (TWS). It transforms complex TWS operations into an intuitive chat interface powered by artificial intelligence, providing real-time monitoring, status queries, and diagnostic capabilities in natural language.

## Root Directory Files

### Core Application Files
- **README.md** - Main project documentation with overview, setup instructions, and key features
- **resync/main.py** - Main entry point for the application with startup validation
- **resync/app_factory.py** - Application factory with lifespan management and component initialization
- **resync/settings.py** - Centralized configuration management using Pydantic BaseSettings
- **resync/lifespan.py** - Application lifespan management with Redis initialization

### Configuration Files
- **settings.toml** - Base application settings
- **settings.development.toml** - Development environment settings
- **settings.production.toml** - Production environment settings
- **settings.test.toml** - Test environment settings
- **pyproject.toml** - Project metadata and dependencies
- **requirements.txt** - Python dependencies
- **.env** - Environment variables
- **.env.example** - Example environment variables

### Documentation Files
- **architecture-diagram.md** - System architecture diagram
- **architecture-optimization-diagram.md** - Optimized architecture diagram
- **architecture-optimization-plan.md** - Architecture optimization plan
- **CODING_STANDARDS.md** - Coding standards and guidelines
- **CONTRIBUTING.md** - Contribution guidelines
- **USE_CASES.md** - Use cases documentation
- **VERSIONING.md** - Versioning strategy

### Security Files
- **SECURITY_CONFIGURATION_GUIDE.md** - Security configuration guide
- **DATABASE_CONNECTION_THRESHOLD_GUIDE.md** - Database connection threshold guide
- **REDIS_WINDOWS_SETUP.md** - Redis setup guide for Windows

### Performance Files
- **PERFORMANCE_OPTIMIZATION_README.md** - Performance optimization documentation
- **PERFORMANCE_SECURITY_OPTIMIZATION.md** - Performance and security optimization
- **MEMORY_BOUNDS_IMPLEMENTATION_SUMMARY.md** - Memory bounds implementation summary
- **CONNECTION_POOL_IMPLEMENTATION_SUMMARY.md** - Connection pool implementation summary

### Testing Files
- **test_*.py** - Various test files for different components
- **pytest.ini** - Pytest configuration
- **pylint.cfg** - Pylint configuration

### Audit and Compliance Files
- **AUDIT_REPORT.json** - Audit report in JSON format
- **AUDIT_REPORT.md** - Audit report in Markdown format
- **CI_CD_IMPROVEMENTS.md** - CI/CD improvements documentation

### Code Quality Files
- **CODE_QUALITY_IMPROVEMENT_FINAL_REPORT.md** - Code quality improvement final report
- **CODE_REVIEW_COMPREHENSIVE.md** - Comprehensive code review
- **PROJECT_QUALITY_IMPROVEMENTS_REPORT.md** - Project quality improvements report

## resync/ Directory

### resync/api/
Contains all API endpoints and related functionality.

- **admin.py** - Administrative endpoints
- **agents.py** - Agent management endpoints
- **audit.py** - Audit-related endpoints
- **auth.py** - Authentication endpoints
- **cache.py** - Cache management endpoints
- **chat.py** - Chat functionality endpoints with WebSocket support
- **health.py** - Health check endpoints
- **performance.py** - Performance monitoring endpoints
- **rag_upload.py** - RAG (Retrieval-Augmented Generation) upload endpoints

#### resync/api/middleware/
- **correlation_id.py** - Correlation ID middleware for request tracing
- **cors_config.py** - CORS configuration middleware
- **csp_middleware.py** - Content Security Policy middleware
- **error_handler.py** - Global error handler middleware

### resync/core/
Core components and services of the application.

- **agent_manager.py** - AI agent management and orchestration
- **async_cache.py** - Asynchronous TTL cache implementation with memory bounds checking
- **connection_manager.py** - WebSocket connection management
- **container.py** - Dependency injection container
- **health_service.py** - Health check service
- **idempotency.py** - Idempotency key management
- **interfaces.py** - Service interfaces for dependency inversion
- **knowledge_graph.py** - Knowledge graph integration (Neo4j)
- **llm_wrapper.py** - Large Language Model wrapper
- **metrics.py** - Runtime telemetry and metrics system
- **redis_init.py** - Redis initialization with connection pooling
- **security_hardening.py** - Security hardening configuration
- **structured_logger.py** - Structured logging system
- **tws_monitor.py** - TWS monitoring service
- **tws_service.py** - TWS service integration

#### resync/core/pools/
Connection pool implementations.

- **base_pool.py** - Base connection pool classes
- **db_pool.py** - Database connection pool
- **http_pool.py** - HTTP connection pool
- **pool_manager.py** - Connection pool manager
- **redis_pool.py** - Redis connection pool

### resync/services/
External service integrations.

- **tws_service.py** - TWS service implementation
- **mock_tws_service.py** - Mock TWS service for testing
- **http_client_factory.py** - HTTP client factory

### resync/models/
Data models and schemas.

- **tws.py** - TWS-related data models

### resync/tool_definitions/
Tool definitions for AI agents.

- **tws_tools.py** - TWS-specific tools for agents

### resync/cqrs/
CQRS (Command Query Responsibility Segregation) implementation.

- **base.py** - Base CQRS classes
- **commands.py** - Command definitions
- **command_handlers.py** - Command handlers
- **dispatcher.py** - Command/query dispatcher
- **queries.py** - Query definitions
- **query_handlers.py** - Query handlers

### resync/RAG/
Retrieval-Augmented Generation data.

- **BASE/** - Base RAG data directory

### resync/security/
Security-related modules.

- **oauth2.py** - OAuth2 implementation

### resync/config/
Configuration files.

- **agents.json** - Agent configurations
- ***.py** - Environment-specific configuration files

## Tests Directory
Contains all test files organized by functionality.

- **test_*.py** - Unit and integration tests
- **api/** - API-specific tests
- **core/** - Core component tests
- **services/** - Service integration tests

## Documentation Directory
Contains detailed documentation files.

- ***.md** - Various documentation files

## Config Directory
Contains configuration files.

- **agents.json** - Agent configurations
- ***.toml** - TOML configuration files

## Data Directory
Contains data files used by the application.

- **mock_tws_data.json** - Mock TWS data for testing

## Scripts Directory
Contains utility scripts.

- ***.py** - Various utility scripts

## Benchmarks Directory
Contains benchmark tests.

- ***.py** - Benchmark test files

## Reports Directory
Contains generated reports.

- ***.md, *.json** - Various reports

## Requirements Directory
Contains requirements files for different environments.

- ***.txt** - Requirements files

## Docs Directory
Contains comprehensive documentation.

- **PERFORMANCE_OPTIMIZATION.md** - Detailed performance optimization guide
- **PERFORMANCE_QUICK_REFERENCE.md** - Quick reference for performance optimization
- **PHASE2_IMPLEMENTATION_SUMMARY.md** - Summary of Phase 2 implementation
- **architecture/** - Architecture documentation
- **security/** - Security documentation

## Static Directory
Contains static assets for the web interface.

- **css/** - Stylesheets
- **js/** - JavaScript files
- **assets/** - Other assets

## Templates Directory
Contains Jinja2 templates for the web interface.

- ***.html** - HTML templates

## Key Features

### 1. AI-Powered Chat Interface
The application provides a natural language interface for interacting with HWA/TWS systems through AI agents.

### 2. Real-Time Monitoring
Comprehensive monitoring of TWS system status, workstations, jobs, and critical paths.

### 3. Security Hardening
Multiple layers of security including:
- Content Security Policy (CSP)
- Rate limiting
- Input validation
- Threat protection
- Authentication and authorization

### 4. Performance Optimization
- Async-first architecture
- Connection pooling
- Smart caching with memory bounds checking
- Resource management
- Resource leak detection
- Auto-scaling capabilities

### 5. Audit and Compliance
- Comprehensive audit logging
- Memory review system
- Compliance reporting
- Security monitoring

### 6. Scalability Features
- Horizontal scaling support
- Connection pooling
- Caching layers
- Resource management

### 7. Advanced Caching
- AsyncTTLCache with TTL support
- Memory bounds checking (100K items, 100MB limit)
- LRU (Least Recently Used) eviction strategy
- Hit rate monitoring and efficiency scoring

### 8. Idempotency Support
- Redis-backed operation deduplication
- Configurable TTL for idempotency keys
- Atomic operation guarantees
- Production-safe fail-fast initialization

## Technology Stack

- **Framework**: FastAPI (async)
- **Database**: Neo4j (Knowledge Graph)
- **Caching**: Redis
- **Frontend**: Jinja2 templates with static assets
- **AI/ML**: LiteLLM integration
- **Monitoring**: Structured logging and metrics
- **Testing**: Pytest
- **Deployment**: Docker support

## Environment-Specific Configurations

The application supports multiple environments:
- Development
- Testing
- Production

Each environment has its own configuration file and can override base settings.

## Security Features

- JWT-based authentication
- Content Security Policy
- CORS configuration
- Input validation and sanitization
- Rate limiting
- Threat detection
- Audit logging
- Secure credential management

## Performance Features

- Asynchronous architecture
- Connection pooling
- Multi-layer caching
- Resource management
- Memory bounds checking
- Performance monitoring
- Health checks
- Auto-scaling capabilities

This documentation provides a comprehensive overview of the Resync project structure and the purpose of its key components.