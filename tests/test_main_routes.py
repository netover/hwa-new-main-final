"""
Comprehensive tests for main application routes and middleware.

This module tests the core Flask application routes, middleware functions,
and integration points to ensure proper functionality and improve test coverage.
"""

import time
import uuid
from unittest.mock import MagicMock, patch

from flask import g


class TestMainRoutes:
    """Test cases for main application routes."""

    def test_login_route(self, client):
        """Test the login page route."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login Page' in response.data

    def test_chat_route_get_method_not_allowed(self, client):
        """Test that GET method is not allowed for chat endpoint."""
        response = client.get('/api/chat')
        assert response.status_code == 405

    def test_chat_route_without_post_data(self, client):
        """Test chat route without POST data."""
        response = client.post('/api/chat')
        # Should return 400 or similar due to missing data
        assert response.status_code in [400, 422]  # Bad Request or Unprocessable Entity


class TestMiddleware:
    """Test cases for middleware functions."""

    def test_before_request_generates_request_id(self, client):
        """Test that before_request middleware generates request ID."""
        # Create a test app instance for testing middleware
        from routes.main import app

        with app.test_request_context('/'):
            # Import and call the before_request function
            from routes.main import before_request

            # Mock request object
            mock_request = MagicMock()
            mock_request.headers.get.return_value = None

            with patch('routes.main.request', mock_request):
                before_request()

                # Check that request_id was set in flask g
                assert hasattr(g, 'request_id')
                assert g.request_id is not None
                assert isinstance(g.request_id, str)

    def test_before_request_uses_existing_request_id(self, client):
        """Test that before_request uses existing X-Request-ID header."""
        from routes.main import app

        with app.test_request_context('/'):
            from routes.main import before_request

            # Mock request object with existing request ID
            existing_id = "test-request-id-123"
            mock_request = MagicMock()
            mock_request.headers.get.return_value = existing_id

            with patch('routes.main.request', mock_request):
                before_request()

                # Check that existing request_id was used
                assert hasattr(g, 'request_id')
                assert g.request_id == existing_id

    def test_before_request_sets_start_time(self, client):
        """Test that before_request sets start time."""
        from routes.main import app

        with app.test_request_context('/'):
            from routes.main import before_request

            mock_request = MagicMock()
            mock_request.headers.get.return_value = None

            with patch('routes.main.request', mock_request):
                before_request()

                # Check that start_time was set in flask g
                assert hasattr(g, 'start_time')
                assert isinstance(g.start_time, float)
                assert g.start_time > 0

    def test_after_request_logs_completion(self, client):
        """Test that after_request middleware logs request completion."""
        from routes.main import app

        with app.test_request_context('/'):
            from routes.main import after_request

            # Set up mock response and g object
            mock_response = MagicMock()
            mock_response.status_code = 200

            # Set required attributes in g
            g.start_time = time.time()
            g.request_id = str(uuid.uuid4())

            # Mock request object
            mock_request = MagicMock()
            mock_request.method = 'GET'
            mock_request.endpoint = 'test_endpoint'
            mock_request.path = '/test'

            with patch('routes.main.request', mock_request):
                with patch('routes.main.log_request_end') as mock_log:
                    after_request(mock_response)

                    # Verify logging was called
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args

                    # Check that all required parameters were passed
                    assert call_args[1]['method'] == 'GET'
                    assert call_args[1]['endpoint'] == 'test_endpoint'
                    assert call_args[1]['status_code'] == 200
                    assert 'duration' in call_args[1]
                    assert 'request_id' in call_args[1]
                    assert call_args[1]['duration'] >= 0

    def test_after_request_handles_missing_start_time(self, client):
        """Test that after_request handles missing start time gracefully."""
        from routes.main import app

        with app.test_request_context('/'):
            from routes.main import after_request

            mock_response = MagicMock()
            mock_response.status_code = 200

            # Don't set start_time in g
            g.request_id = str(uuid.uuid4())

            mock_request = MagicMock()
            mock_request.method = 'GET'
            mock_request.endpoint = 'test_endpoint'
            mock_request.path = '/test'

            with patch('routes.main.request', mock_request):
                with patch('routes.main.log_request_end') as mock_log:
                    # Should not raise an exception
                    after_request(mock_response)

                    # Logging should still be called with duration=0
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args[1]
                    assert call_args['duration'] == 0

    def test_exception_handler_logs_unhandled_exception(self, client):
        """Test that exception handler logs unhandled exceptions."""
        from routes.main import app

        with app.test_request_context('/'):
            from routes.main import handle_exception

            # Create a test exception
            test_exception = ValueError("Test error")

            # Set up g object with required attributes
            g.start_time = time.time()
            g.request_id = str(uuid.uuid4())

            # Mock request object
            mock_request = MagicMock()
            mock_request.method = 'GET'
            mock_request.endpoint = 'test_endpoint'
            mock_request.path = '/test'

            with patch('routes.main.request', mock_request):
                with patch('routes.main.log_error') as mock_log:
                    result = handle_exception(test_exception)

                    # Verify logging was called
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args

                    # Check that exception and context were logged
                    assert call_args[0][0] == test_exception  # exception
                    assert call_args[1]['method'] == 'GET'
                    assert call_args[1]['endpoint'] == 'test_endpoint'
                    assert 'duration' in call_args[1]
                    assert 'request_id' in call_args[1]

                    # Check return value
                    assert result == ("Internal Server Error", 500)

    def test_exception_handler_handles_missing_start_time(self, client):
        """Test that exception handler handles missing start time."""
        from routes.main import app

        with app.test_request_context('/'):
            from routes.main import handle_exception

            test_exception = ValueError("Test error")

            # Don't set start_time but set request_id
            g.request_id = str(uuid.uuid4())

            mock_request = MagicMock()
            mock_request.method = 'GET'
            mock_request.endpoint = 'test_endpoint'
            mock_request.path = '/test'

            with patch('routes.main.request', mock_request):
                with patch('routes.main.log_error') as mock_log:
                    # Should not raise an exception
                    handle_exception(test_exception)

                    # Logging should be called with duration=0
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args[1]
                    assert call_args['duration'] == 0


class TestFlaskAppIntegration:
    """Integration tests for the Flask application."""

    def test_app_registers_api_blueprint(self, client):
        """Test that the API blueprint is registered."""
        from routes.main import app
        # Check that the blueprint is registered
        assert 'api' in app.blueprints

    def test_app_has_socketio_initialized(self, client):
        """Test that SocketIO is initialized with the app."""
        from routes.main import socketio
        # SocketIO should be initialized (we can't easily test the actual initialization)
        assert socketio is not None

    def test_app_has_error_handler(self, client):
        """Test that the app has the exception error handler registered."""
        from routes.main import app
        # Check that the error handler is registered for Exception
        handlers = app.error_handler_spec[None][None]
        assert Exception in handlers

    def test_middleware_functions_registered(self, client):
        """Test that middleware functions are registered with the app."""
        from routes.main import app
        # Check that before_request and after_request are registered
        assert len(app.before_request_funcs[None]) > 0
        assert len(app.after_request_funcs[None]) > 0


class TestLoggingContext:
    """Test cases for LoggingContext usage in routes."""

    def test_login_route_uses_logging_context(self, client):
        """Test that login route uses LoggingContext properly."""
        from routes.main import app

        with app.test_request_context('/login'):
            from routes.main import login

            # Mock the LoggingContext
            with patch('routes.main.LoggingContext') as mock_context:
                with patch('routes.main.log_info') as mock_log:
                    login()

                    # Check that LoggingContext was used
                    mock_context.assert_called_once()
                    call_args = mock_context.call_args[1]
                    assert 'action' in call_args
                    assert 'request_id' in call_args

                    # Check that logging was called
                    mock_log.assert_called_once()

    def test_chat_route_uses_logging_context(self, client):
        """Test that chat route uses LoggingContext properly."""
        from routes.main import app

        with app.test_request_context('/api/chat', method='POST'):
            from routes.main import chat

            # Mock request and LoggingContext
            mock_request = MagicMock()
            mock_request.method = 'POST'

            with patch('routes.main.request', mock_request):
                with patch('routes.main.LoggingContext') as mock_context:
                    with patch('routes.main.log_info') as mock_log:
                        with patch('routes.main.abort'):  # Prevent actual abort
                            try:
                                chat()
                            except:
                                pass  # We expect this to fail due to mocking

                            # Check that LoggingContext was used
                            mock_context.assert_called_once()
                            call_args = mock_context.call_args[1]
                            assert 'action' in call_args
                            assert 'request_id' in call_args

                            # Check that logging was called
                            mock_log.assert_called_once()
