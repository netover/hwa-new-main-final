"""Base Gunicorn configuration for Resync application."""

import os
import multiprocessing

from resync.config.settings import settings


# Server socket
bind = f"0.0.0.0:{settings.port}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 30
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "resync"

# Server mechanics
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None

# Worker temp directory
worker_tmp_dir = "/dev/shm"

# Hooks
def when_ready(server):
    """Called when the server is ready to accept connections."""
    server.log.info("Resync server is ready. Listening on %s", server.address)


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)


def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info("Worker exited (pid: %s)", worker.pid)


def child_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info("Child worker exited (pid: %s)", worker.pid)


def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Resync server")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Resync server")


def worker_abort(worker):
    """Called when a worker aborted to load the application."""
    worker.log.info("Worker aborted (pid: %s)", worker.pid)


def pre_exec(server):
    """Called just before the master process is initialized."""
    server.log.info("Master process is about to start")


# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
tornado = False
raw_env = []
paste = None
on_exit = None


def get_num_workers():
    """Calculate optimal number of workers based on system resources."""
    cpu_count = multiprocessing.cpu_count()
    
    # Rule of thumb: (2 * CPU_COUNT) + 1 for I/O bound applications
    # For CPU bound, use CPU_COUNT
    # For mixed, use between CPU_COUNT and (2 * CPU_COUNT) + 1
    
    if settings.is_production:
        # Production: more workers for better concurrency
        return min(cpu_count * 2 + 1, 8)  # Cap at 8 to avoid excessive memory usage
    else:
        # Development: fewer workers for easier debugging
        return min(cpu_count, 4)


# Apply calculated worker count
workers = get_num_workers()


def get_worker_class():
    """Get appropriate worker class based on environment."""
    if settings.is_production:
        return "uvicorn.workers.UvicornWorker"
    else:
        return "uvicorn.workers.UvicornWorker"


# Apply worker class
worker_class = get_worker_class()


def get_timeout():
    """Get appropriate timeout based on environment."""
    if settings.is_production:
        return 30  # Production: shorter timeout for better responsiveness
    else:
        return 60  # Development: longer timeout for debugging


# Apply timeout
timeout = get_timeout()


def get_keepalive():
    """Get appropriate keepalive timeout."""
    # Keep connections alive for reuse, but not too long
    return 5


# Apply keepalive
keepalive = get_keepalive()




