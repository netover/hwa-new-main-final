"""Staging Gunicorn configuration for Resync application."""

from .base import *

# Staging-specific overrides
import multiprocessing

# Intermediate worker count for staging
cpu_count = multiprocessing.cpu_count()
workers = min(cpu_count + 1, 6)  # Between dev and prod
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 45  # Intermediate timeout
keepalive = 3  # Intermediate keepalive
max_requests = 500  # Restart more frequently than prod
max_requests_jitter = 50

# Staging logging (more verbose than prod, less than dev)
loglevel = "info"
accesslog = "-"  # Will be overridden by Docker logging
errorlog = "-"   # Will be overridden by Docker logging
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s '
    '"{X-Request-ID}o" "{X-Correlation-ID}o" %(L)s'
)

# Performance settings for staging
worker_connections = 500  # Between dev and prod
backlog = 1024  # Intermediate backlog
preload_app = True  # Preload app for consistency with production

# Security settings (intermediate)
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Staging hooks
def when_ready_staging(server):
    """Called when the server is ready to accept connections."""
    server.log.info(
        "Resync staging server is ready. Listening on %s", 
        server.address
    )
    server.log.info("Staging mode: Production-like configuration with enhanced logging")
    server.log.info("Workers: %d", workers)
    server.log.info("Access API at http://localhost:%s/docs", server.address[1])


def post_fork_staging(server, worker):
    """Called just after a worker has been forked."""
    worker.log.info("Staging worker spawned (pid: %s)", worker.pid)
    worker.log.info("Worker connections limit: %d", worker_connections)


def pre_fork_staging(server, worker):
    """Called just before a worker is forked."""
    server.log.info("About to fork staging worker (pid: %s)", worker.pid)


def worker_exit_staging(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(
        "Staging worker exited (pid: %s, exit code: %s)", 
        worker.pid, getattr(worker, 'exit_code', 'unknown')
    )


# Staging-specific environment variables
raw_env = [
    "RESYNC_ENV=staging",
    "RESYNC_DEBUG=false",
    "RESYNC_LOG_LEVEL=info",
    "PYTHONUNBUFFERED=1",
    "RESYNC_MAX_WORKERS=" + str(workers),
]

# Process naming
proc_name = "resync-staging"

# Daemon mode (typically handled by Docker)
daemon = False

# SSL settings (can be enabled for staging SSL testing)
keyfile = os.environ.get("RESYNC_SSL_KEY", None)
certfile = os.environ.get("RESYNC_SSL_CERT", None)

# Graceful shutdown settings
graceful_timeout = 30  # Same as production
worker_tmp_dir = "/dev/shm"  # Use shared memory for consistency

# Memory optimization (more aggressive than production for testing)
max_requests = 500  # Restart more frequently to catch memory issues
max_requests_jitter = 25  # Add jitter to prevent synchronized restarts

# Monitoring and health checks
def on_starting_staging(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Resync staging server")
    server.log.info("Configuration loaded for staging environment")


def on_reload_staging(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Resync staging server")
    server.log.info("Workers will be recycled gracefully")


# Additional staging optimizations
# Enable TCP_NODELAY for consistency with production
tcp_nodelay = True

# Enable keep-alive for consistency with production
keepalive = 3

# Worker process settings
worker_tmp_dir = "/dev/shm"  # Use memory-mapped temp directory

# Security hardening (same as production)
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Override hooks for staging
when_ready = when_ready_staging
post_fork = post_fork_staging
pre_fork = pre_fork_staging
worker_exit = worker_exit_staging
on_starting = on_starting_staging
on_reload = on_reload_staging

# Staging-specific settings for testing
# Enable some debug features that are disabled in production
# but keep performance similar to production

# Slightly more relaxed timeouts for testing
timeout = 45

# Enable detailed logging for debugging
loglevel = "info"

# Performance monitoring enabled
statsd_host = os.environ.get("STATSD_HOST", "localhost")
statsd_prefix = "resync.staging"




