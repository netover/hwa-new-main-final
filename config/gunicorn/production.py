"""Production Gunicorn configuration for Resync application."""

from .base import *

# Production-specific overrides
import multiprocessing

# Optimized worker count for production
cpu_count = multiprocessing.cpu_count()
workers = min(cpu_count * 2 + 1, 8)  # Cap at 8 workers
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 30  # Standard timeout for production
keepalive = 5  # Optimize keep-alive for production
max_requests = 1000  # Restart workers after 1000 requests
max_requests_jitter = 100  # Add jitter to prevent thundering herd

# Production logging
loglevel = "info"
accesslog = "-"  # Will be overridden by Docker logging
errorlog = "-"   # Will be overridden by Docker logging
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s '
    '"{X-Request-ID}o" "{X-Correlation-ID}o" %(L)s'
)

# Performance optimizations for production
worker_connections = 1000  # Higher connection limit
backlog = 2048  # Larger backlog for traffic spikes
preload_app = True  # Preload app for memory efficiency

# Security settings (strict for production)
limit_request_line = 4094  # Standard HTTP limit
limit_request_fields = 100  # Standard limit
limit_request_field_size = 8190  # Standard limit

# Production hooks
def when_ready_prod(server):
    """Called when the server is ready to accept connections."""
    server.log.info(
        "Resync production server is ready. Listening on %s", 
        server.address
    )
    server.log.info("Production mode: Optimized for performance and security")
    server.log.info("Workers: %d", workers)
    server.log.info("Worker class: %s", worker_class)


def post_fork_prod(server, worker):
    """Called just after a worker has been forked."""
    worker.log.info("Production worker spawned (pid: %s)", worker.pid)
    worker.log.info("Worker connections limit: %d", worker_connections)


def pre_fork_prod(server, worker):
    """Called just before a worker is forked."""
    server.log.info("About to fork production worker (pid: %s)", worker.pid)


def worker_exit_prod(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(
        "Production worker exited (pid: %s, exit code: %s)", 
        worker.pid, getattr(worker, 'exit_code', 'unknown')
    )


# Production-specific environment variables
raw_env = [
    "RESYNC_ENV=production",
    "RESYNC_DEBUG=false",
    "RESYNC_LOG_LEVEL=info",
    "PYTHONUNBUFFERED=1",
    "RESYNC_MAX_WORKERS=" + str(workers),
]

# Process naming
proc_name = "resync-prod"

# Daemon mode (typically handled by systemd/supervisor in production)
daemon = False  # Let Docker/systemd handle daemonization

# SSL settings (configure as needed)
keyfile = os.environ.get("RESYNC_SSL_KEY", None)
certfile = os.environ.get("RESYNC_SSL_CERT", None)

# Graceful shutdown settings
graceful_timeout = 30  # Allow 30 seconds for graceful shutdown
worker_tmp_dir = "/dev/shm"  # Use shared memory for better performance

# Memory optimization
max_requests = 1000  # Restart workers to prevent memory leaks
max_requests_jitter = 50  # Add jitter to prevent synchronized restarts

# Monitoring and health checks
def on_starting_prod(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Resync production server")
    server.log.info("Configuration loaded for production environment")


def on_reload_prod(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Resync production server")
    server.log.info("Workers will be recycled gracefully")


# Additional production optimizations
# Enable TCP_NODELAY for better latency
tcp_nodelay = True

# Enable keep-alive for better performance
keepalive = 5

# Worker process settings
worker_tmp_dir = "/dev/shm"  # Use memory-mapped temp directory

# Security hardening
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Override hooks for production
when_ready = when_ready_prod
post_fork = post_fork_prod
pre_fork = pre_fork_prod
worker_exit = worker_exit_prod
on_starting = on_starting_prod
on_reload = on_reload_prod
