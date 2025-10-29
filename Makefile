# Makefile for the Resync Project
# Provides a set of commands to manage the application lifecycle.

# --- Variables ---
# Use the project's virtual environment's Python interpreter
PYTHON = .venv/bin/python
PIP = .venv/bin/pip
AGNO = .venv/bin/agno
# Define the source directory for formatting and linting
SRC_DIR = resync tests

# --- Environment Setup ---
.PHONY: venv
venv:
	@echo "--- Creating virtual environment in .venv ---"
	python3 -m venv .venv
	@echo "--- Virtual environment created. Activate with 'source .venv/bin/activate' ---"

.PHONY: install
install: venv
	@echo "--- Installing dependencies from requirements/dev.txt ---"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/dev.txt
	@echo "--- Installing Playwright browsers ---"
	.venv/bin/playwright install --with-deps
	@echo "--- Installation complete ---"

# --- Code Quality & Formatting ---
.PHONY: format
format:
	@echo "--- Formatting code with Black and Ruff ---"
	$(PYTHON) -m black $(SRC_DIR)
	$(PYTHON) -m ruff format $(SRC_DIR)

.PHONY: lint
lint:
	@echo "--- Linting with Flake8 ---"
	$(PYTHON) -m flake8 $(SRC_DIR)
	@echo "--- Linting with Ruff ---"
	$(PYTHON) -m ruff check $(SRC_DIR)
	@echo "--- Type-checking with MyPy ---"
	$(PYTHON) -m mypy $(SRC_DIR)

.PHONY: security
security:
	@echo "--- Running Bandit security scan ---"
	$(PYTHON) -m bandit -r resync/ tests/ -c pyproject.toml
	@echo "--- Running Safety vulnerability check ---"
	$(PYTHON) -m safety check --full-report

.PHONY: check
check: format lint security

# --- Application Lifecycle ---
.PHONY: run
run:
	@echo "--- Starting Resync application with Uvicorn ---"
	.venv/bin/uvicorn resync.main:app --reload

.PHONY: run-llm
run-llm:
	@echo "--- Starting local LLM server ---"
	$(AGNO) llm --model-path $(LLM_MODEL_PATH)

# --- Configuration Management ---
.PHONY: env
env:
	@echo "--- Generating .env.example from settings ---"
	$(AGNO) settings resync.settings:settings > .env.example
	@echo ".env.example file has been generated. Please review and create a .env file."

# --- Testing ---
.PHONY: test
test:
	@echo "--- Running pytest test suite ---"
	$(PYTHON) -m pytest

.PHONY: test-specific
test-specific:
	@echo "--- Running specific test with full diagnostics ---"
	$(PYTHON) -m pytest -v -s --tb=long \
		--log-cli-level=DEBUG \
		--capture=no \
		--durations=10 \
		tests/core/test_connection_pool_monitoring.py::TestConnectionPoolMetrics::test_pool_statistics_accuracy

.PHONY: test-env
test-env:
	@echo "--- Checking test environment health ---"
	@$(PYTHON) -c "import aiofiles; import pytest_asyncio; import structlog; print('✅ Core dependencies OK')" || (echo "❌ Missing dependencies" && exit 1)
	@$(PYTHON) -m pytest --collect-only tests/ > /dev/null && echo "✅ Test discovery OK" || (echo "❌ Test discovery failed" && exit 1)
	@echo "--- Environment health check complete ---"

.PHONY: test-isolated
test-isolated:
	@echo "--- Running test in isolated container ---"
	@if docker build -f Dockerfile.test -t pool-test . 2>/dev/null; then \
		docker run --rm pool-test make test-specific; \
		docker rmi pool-test 2>/dev/null; \
	else \
		echo "❌ Failed to build/run container test - trying alternative..."; \
		uv run pytest tests/core/test_connection_pool_monitoring.py::TestConnectionPoolMetrics::test_pool_statistics_accuracy -v; \
	fi

.PHONY: migrate-to-uv
migrate-to-uv:
	@echo "--- Migrating from Poetry to uv ---"
	@if [ -f "pyproject.toml" ] && [ -f "poetry.lock" ]; then \
		echo "Found Poetry configuration, migrating..."; \
		uvx migrate-to-uv --dependency-groups-strategy set-default-groups --keep-current-data; \
		uv sync --all-extras --dev; \
		echo "✅ Migration complete!"; \
	else \
		echo "No Poetry configuration found, ensuring uv setup..."; \
		uv sync --all-extras --dev; \
	fi

# --- Housekeeping ---
.PHONY: clean
clean:
	@echo "--- Cleaning up project ---"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache

.PHONY: help
help:
	@echo "--- Resync Project Makefile ---"
	@echo "Available commands:"
	@echo "  venv          - Create a Python virtual environment."
	@echo "  install       - Install all project dependencies."
	@echo "  format        - Format code using Black and Ruff."
	@echo "  lint          - Lint code with Flake8, Ruff, and type-check with MyPy."
	@echo "  security      - Run Bandit and Safety security checks."
	@echo "  check         - Run format, lint, and security checks."
	@echo "  run           - Start the FastAPI application."
	@echo "  run-llm       - Start the local LLM server."
	@echo "  env           - Generate the .env.example file."
	@echo "  test          - Run the pytest test suite."
	@echo "  clean         - Remove temporary files and the virtual environment."
	@echo "--------------------------------"
