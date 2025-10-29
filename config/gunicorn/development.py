"""Development Gunicorn configuration for Resync application."""

from .base import *

# Development-specific overrides
workers = 1  # Single worker for easier debugging
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60  # Longer timeout for debugging
keepalive = 2  # Shorter keepalive for development
max_requests = 100  # Restart workers more frequently in dev
max_requests_jitter = 10

# Enhanced logging for development
loglevel = "debug"
accesslog = "-"
errorlog = "-"
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s '
    '"{X-Request-ID}o" "{X-Correlation-ID}o"'
)

# Auto-reload for development
# Note: This requires the gunicorn --reload flag
reload = False  # Will be set via command line

# Performance settings for development
worker_connections = 100  # Lower for dev
backlog = 512

# Security settings (relaxed for development)
limit_request_line = 8192  # Larger for debugging
limit_request_fields = 200
limit_request_field_size = 16384

# Development hooks
def when_ready_dev(server):
    """Called when the server is ready to accept connections."""
    server.log.info(
        "Resync development server is ready. Listening on %s", 
        server.address
    )
    server.log.info("Development mode: Debug logging enabled")
    server.log.info("Access API at http://localhost:%s/docs", server.address[1])


def post_fork_dev(server, worker):
    """Called just after a worker has been forked."""
    worker.log.info("Development worker spawned (pid: %s)", worker.pid)
    worker.log.info("Debug mode: All logs will be shown")


# Development-specific environment variables
raw_env = [
    "RESYNC_ENV=development",
    "RESYNC_DEBUG=true",
    "RESYNC_LOG_LEVEL=debug",
]

# Process naming
proc_name = "resync-dev"

# No daemon mode in development
daemon = False

# SSL disabled in development
keyfile = None
certfile = None
