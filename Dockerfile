# --- Stage 1: Build Stage ---
# Use a Python base image with build tools
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /app

# Install build dependencies (e.g., for packages that compile from source)
# This is a good practice even if not immediately needed.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential

# Install Poetry for dependency management
RUN pip install poetry

# Copy only the files needed for dependency installation to leverage Docker caching
COPY poetry.lock pyproject.toml ./

# Install dependencies into a virtual environment
# --no-root: don't install the project itself, only dependencies
# --no-dev: exclude development dependencies like pytest
RUN poetry install --no-root --no-dev

# --- Stage 2: Runtime Stage ---
# Use a slim Python base image for a smaller final image size
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Set environment variables
# Tell Python not to write .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure Python output is sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED 1

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Set the PATH to include the venv's bin directory
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY ./resync ./resync
COPY ./config ./config
COPY ./static ./static
COPY ./templates ./templates

# Expose the port the application will run on
EXPOSE 8000

# Configure a simple healthcheck.  This instructs the container runtime to
# periodically check the /health endpoint to verify that the API is up
# and responding.  The interval, timeout and retries are conservative
# defaults and may be tuned in production environments.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD [ "sh", "-c", "wget -qO- http://localhost:8000/health || exit 1" ]

# The command to run the application using Gunicorn+Uvicorn for production
# It will be run by a container orchestration system (e.g., Docker Compose, Kubernetes)
# Use different configurations based on environment
CMD ["sh", "-c", "if [ \"$RESYNC_ENV\" = \"production\" ]; then gunicorn --config python:config.gunicorn.production resync.main:app; elif [ \"$RESYNC_ENV\" = \"staging\" ]; then gunicorn --config python:config.gunicorn.staging resync.main:app; else gunicorn --config python:config.gunicorn.development --reload resync.main:app; fi"]
