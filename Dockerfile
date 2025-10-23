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

# The command to run the application using Uvicorn
# It will be run by a container orchestration system (e.g., Docker Compose, Kubernetes)
CMD ["uvicorn", "resync.main:app", "--host", "0.0.0.0", "--port", "8000"]
