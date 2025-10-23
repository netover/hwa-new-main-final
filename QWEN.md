# Resync: AI-Powered HWA/TWS Interface - Project Context

## Project Overview

Resync is an AI-powered interface for HCL Workload Automation (HWA), formerly known as IBM Tivoli Workload Scheduler (TWS). It transforms complex TWS operations into an intuitive chat interface powered by artificial intelligence, providing real-time monitoring, status queries, and diagnostic capabilities in natural language.

The project is built with Python 3.13+, FastAPI, and leverages AI agents to interact with the TWS system, combining live status from TWS with contextual knowledge from an integrated knowledge base using Retrieval-Augmented Generation (RAG).

## Architecture

The system follows a multi-layer architecture:

1. **User Interface Layer**: Chatbot interface and dashboard for operators
2. **AI Agent System**: Manages specialized agents for different tasks
3. **Knowledge Graph**: RAG system with semantic search capabilities
4. **TWS Integration Layer**: Real-time API client for HWA/TWS operations
5. **External Services**: Validation, audit, and monitoring systems

Key technologies include:
- Web Framework: FastAPI
- AI/LLM Integration: Litellm, various AI models
- Data Storage: PostgreSQL, Redis, Qdrant Vector DB
- Monitoring: Prometheus metrics
- Security: OAuth2, JWT, CSP middleware

## Key Features

- **Natural Language Queries**: Ask questions like "What's the status of job XYZ?" in plain language
- **Real-time Dashboard**: Monitor system status, engine health, and job statuses
- **AI-Powered Diagnostics**: Automatic problem identification with solutions
- **Knowledge Graph Integration**: Combines live TWS data with documented procedures
- **Secure Architecture**: Read-only operations, rate limiting, CORS protection
- **Production-Ready**: Comprehensive monitoring, health checks, and logging

## Security Improvements

### Credential Management
- Removed hardcoded credentials from configuration files
- Implemented secure credential validation during startup
- Added requirements for environment-specific credential values

### Authentication System
- Implemented JWT-based authentication system
- Created proper login endpoint with secure credential validation
- Added CSRF protection and secure session management

### CORS Configuration Security
- Enhanced CORS configuration with strict validation
- Implemented per-environment CORS policies
- Added security monitoring for CORS violations

## Performance Optimizations

### AsyncTTLCache Improvements
- Enhanced memory management with better size estimation
- Implemented LRU eviction when cache bounds are exceeded
- Added more accurate memory usage tracking

### Connection Pool Optimization
- Improved Redis connection pool settings
- Enhanced database connection pool configuration
- Optimized HTTP connection pool for external API calls

### Resource Management
- Added centralized resource manager for proper lifecycle management
- Implemented proper shutdown and cleanup procedures
- Enhanced resource tracking and monitoring

## Error Handling Improvements

### Standardized Error Handling Patterns
- Created consistent error handling across all components
- Implemented proper exception hierarchies
- Standardized error response formats

### API Error Responses
- Implemented comprehensive error response models
- Added troubleshooting hints to error responses
- Enhanced logging with correlation IDs

## Code Quality Enhancements

### Code Duplication Removal
- Created shared utility modules for common functionality
- Implemented reusable error handling decorators
- Centralized common patterns

### Function Complexity Reduction
- Broke down complex functions into smaller, manageable pieces
- Improved maintainability and readability
- Enhanced testability of components

### Type Annotation Improvements
- Added comprehensive type annotations throughout the codebase
- Enhanced type safety with proper generics
- Improved IDE support and static analysis

## Architectural Improvements

### Dependency Injection System
- Enhanced service registration and resolution
- Added better error handling for missing services
- Improved factory functions for complex dependencies

### Middleware Optimization
- Added performance monitoring to error handler middleware
- Enhanced logging and correlation tracking
- Improved security monitoring

## Files and Directories

- `resync/`: Main application source code
- `tests/`: Test suite with unit and integration tests
- `config/`: Configuration files
- `templates/`: HTML templates for the dashboards
- `static/`: Static assets (CSS, JS, images)
- `rag/`: Documents for the RAG (Retrieval-Augmented Generation) system
- `docs/`: Documentation files
- `chroma/`: ChromaDB vector storage
- `logs/`: Application log files
- `reports/`: Test and analysis reports

## Development Setup

### Prerequisites
- Python 3.13+
- Access to HCL Workload Automation environment (or mock mode)

### Environment Setup
1. Create a virtual environment: `python -m venv .venv`
2. Activate it: `source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Create `.env` file from `.env.example`
5. Configure environment variables for TWS connection and LLM providers

### Configuration
The application uses Dynaconf for configuration management and loads settings from:
- `settings.toml`: Base settings
- `settings.{environment}.toml`: Environment-specific overrides
- Environment variables with `APP_` prefix

Key configuration areas:
- TWS connection settings (host, port, credentials)
- LLM provider configuration (OpenAI, Ollama, OpenRouter, etc.)
- Database and cache settings
- Security settings (CORS, CSP)

## Building and Running

### Development Mode
```bash
# Run with mock TWS data
uvicorn resync.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
# Run with real TWS connection
uvicorn resync.main:app --host 0.0.0.0 --port 8000
```

### Docker
The project includes a Dockerfile for containerization:
```bash
docker build -t resync .
docker run -p 8000:8000 resync
```

### Make Commands
The project includes a Makefile with common commands:
- `make install`: Install dependencies
- `make run`: Run the application
- `make test`: Run tests
- `make format`: Format code with Black/Ruff
- `make lint`: Run linting and type checking
- `make security`: Run security scans
- `make check`: Run format, lint, and security checks

## Testing

The project has a comprehensive testing setup:
- Unit tests using pytest
- Integration tests for API endpoints
- Mutation testing with mutmut
- Performance testing with Locust
- Security testing with Bandit

Run tests with:
```bash
make test
```

## Development Conventions

### Coding Standards
- Code follows PEP 8 style guidelines
- Type hints are used throughout
- Async/await patterns for I/O operations
- Dependency injection for testability
- Comprehensive error handling and logging

### Error Handling
- Custom exception hierarchy with ResyncException as base
- Consistent error response format
- Correlation IDs for request tracing
- Comprehensive logging with structured metadata

### Security Measures
- Content Security Policy (CSP) middleware
- Rate limiting with Redis backend
- Input validation and sanitization
- Secure configuration management
- Environment-specific security policies

### Performance
- Asynchronous TTL cache with sharded locking
- Redis connection pooling
- Database connection pooling
- Health checks for system stability
- Metrics collection with Prometheus

## Key Files to Understand

- `resync/main.py`: Main FastAPI application entry point
- `resync/settings.py`: Configuration management with Dynaconf
- `resync/core/async_cache.py`: Asynchronous caching implementation
- `resync/api/chat.py`: WebSocket chat endpoints
- `resync/api/agents.py`: AI agent system integration
- `resync/api/middleware/`: Security and performance middleware
- `pyproject.toml`: Project dependencies and tool configuration
- `settings.toml`: Base application settings

## Special Considerations

1. The system supports both real TWS connections and mock mode for development
2. LLM providers are configurable (OpenAI, Ollama, OpenRouter, etc.)
3. The application includes comprehensive monitoring and health checks
4. Security is implemented at multiple levels (CORS, CSP, rate limiting)
5. The architecture supports horizontal scaling with Redis and stateless workers