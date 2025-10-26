"""
Main Application Routes

This module defines the main application routes and initializes the Flask app.
"""

from flask import Flask, request, abort, g
import time
import uuid
from .api import api
from .websocket import socketio

# Structured logging integration
from config.structured_logging_basic import (
    LoggingContext, log_request_end,
    log_error, log_info
)

app = Flask(__name__)
app.register_blueprint(api)

# Initialize SocketIO with the app
socketio.init_app(app)

# Request ID middleware (must be after app initialization)
@app.before_request
def before_request():
    """Generate and store request ID for each request."""
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    g.request_id = request_id
    g.start_time = time.time()

@app.after_request
def after_request(response):
    """Log request completion."""
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        log_request_end(
            method=request.method,
            endpoint=request.endpoint or request.path,
            status_code=response.status_code,
            duration=duration,
            request_id=getattr(g, 'request_id', None)
        )
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Log unhandled exceptions."""
    duration = time.time() - g.start_time if hasattr(g, 'start_time') else 0
    log_error(
        e,
        "Unhandled exception occurred",
        method=request.method,
        endpoint=request.endpoint or request.path,
        request_id=getattr(g, 'request_id', None),
        duration=duration
    )
    return "Internal Server Error", 500

@app.route('/login')
def login() -> str:
    request_id = getattr(g, 'request_id', None)
    with LoggingContext(
        action="login_page_access",
        request_id=request_id
    ):
        log_info("Login page accessed")
        return 'Login Page'

@app.route('/api/chat', methods=['POST'])
def chat() -> None:
    if request.method != 'POST':
        abort(405, description='Method Not Allowed - Use POST')
    request_id = getattr(g, 'request_id', None)
    with LoggingContext(
        action="chat_request",
        request_id=request_id
    ):
        log_info("Chat request received", method=request.method)
        # Process chat message"""