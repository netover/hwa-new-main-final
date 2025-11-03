"""Cache middleware with ETag and 304 Not Modified support."""

import hashlib
import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .policies import (
    EnvironmentCacheConfig,
    get_cache_control_header,
    get_etag_header,
    get_ttl_for_path,
    should_compress_response,
)


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add caching headers, ETags, and 304 support.
    
    Features:
    - Automatic ETag generation for responses
    - 304 Not Modified support with If-None-Match
    - Cache-Control headers based on environment policies
    - Content compression based on content type and size
    - Last-Modified headers
    - Vary headers for proper caching
    """
    
    def __init__(self, app: Callable, skip_paths: Optional[list] = None):
        super().__init__(app)
        self.skip_paths = skip_paths or ["/health", "/metrics", "/ping"]
        self.config = EnvironmentCacheConfig.get_config()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add caching headers."""
        
        # Skip caching for certain paths
        if self._should_skip_caching(request):
            return await call_next(request)
        
        # Handle 304 Not Modified requests
        if_none_match = request.headers.get("if-none-match")
        if_modified_since = request.headers.get("if-modified-since")
        
        response = await call_next(request)
        
        # Skip caching for non-cacheable responses
        if self._should_not_cache_response(response):
            return response
        
        # Generate ETag if content is cacheable
        if self.config["etag_enabled"] and response.body:
            etag = self._generate_etag(response.body)
            response.headers["etag"] = etag
            
            # Check for 304 condition
            if if_none_match and self._etags_match(if_none_match, etag):
                return Response(
                    status_code=304,
                    headers={
                        "etag": etag,
                        "cache-control": response.headers.get("cache-control", ""),
                    }
                )
            
            # Check for If-Modified-Since condition
            if (if_modified_since and 
                self.config["last_modified_enabled"] and 
                hasattr(response, 'last_modified')):
                if self._not_modified_since(if_modified_since, response.last_modified):
                    return Response(
                        status_code=304,
                        headers={
                            "etag": etag,
                            "last-modified": response.last_modified,
                            "cache-control": response.headers.get("cache-control", ""),
                        }
                    )
        
        # Add caching headers
        self._add_cache_headers(request, response)
        
        # Add compression
        if (should_compress_response(len(response.body) if response.body else 0, 
                               response.headers.get("content-type", ""))):
            response = await self._compress_response(response)
        
        return response
    
    def _should_skip_caching(self, request: Request) -> bool:
        """Check if caching should be skipped for this request."""
        path = request.url.path
        
        # Skip specific paths
        for skip_path in self.skip_paths:
            if path.startswith(skip_path):
                return True
        
        # Skip non-GET/HEAD requests
        if request.method not in ("GET", "HEAD"):
            return True
        
        # Skip if no-cache header is present
        if "no-cache" in request.headers.get("cache-control", ""):
            return True
        
        return False
    
    def _should_not_cache_response(self, response: Response) -> bool:
        """Check if response should not be cached."""
        # Don't cache error responses (except 404 for some cases)
        if response.status_code >= 500:
            return True
        
        # Don't cache streaming responses
        if hasattr(response, 'streaming') and response.streaming:
            return True
        
        # Don't cache if already explicitly set
        cache_control = response.headers.get("cache-control", "")
        if "no-store" in cache_control or "private" in cache_control:
            return True
        
        # Don't cache if no content
        if not response.body:
            return True
        
        return False
    
    def _generate_etag(self, content: bytes) -> str:
        """Generate ETag for content."""
        return get_etag_header(content, weak=False)
    
    def _etags_match(self, if_none_match: str, etag: str) -> bool:
        """Check if ETags match (supports wildcards)."""
        if if_none_match == "*":
            return True
        
        # Remove quotes and W/ prefixes for comparison
        client_etags = [tag.strip().strip('"') for tag in if_none_match.split(",")]
        server_etag = etag.strip().strip('"')
        
        return server_etag in client_etags
    
    def _not_modified_since(self, if_modified_since: str, last_modified: str) -> bool:
        """Check if resource hasn't been modified since."""
        try:
            from email.utils import parsedate_to_datetime
            from datetime import timezone
            
            client_time = parsedate_to_datetime(if_modified_since)
            server_time = parsedate_to_datetime(last_modified)
            
            if client_time and server_time:
                # Normalize to UTC
                if client_time.tzinfo is None:
                    client_time = client_time.replace(tzinfo=timezone.utc)
                if server_time.tzinfo is None:
                    server_time = server_time.replace(tzinfo=timezone.utc)
                
                return server_time <= client_time
        except Exception:
            # If parsing fails, assume content has been modified
            pass
        
        return False
    
    def _add_cache_headers(self, request: Request, response: Response) -> None:
        """Add appropriate caching headers to response."""
        path = request.url.path
        
        # Determine if content is private (user-specific)
        is_private = self._is_private_content(request, path)
        
        # Get TTL for this path
        ttl = get_ttl_for_path(path, is_private)
        
        # Skip if TTL is 0 (no cache)
        if ttl == 0:
            response.headers["cache-control"] = "no-store, no-cache, must-revalidate"
            return
        
        # Add Cache-Control header
        if self.config["cache_control_headers"]:
            cache_control = get_cache_control_header(ttl, is_private)
            response.headers["cache-control"] = cache_control
        
        # Add Last-Modified header
        if self.config["last_modified_enabled"]:
            if not hasattr(response, 'last_modified') or not response.last_modified:
                # Generate Last-Modified from current time
                last_modified = time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", 
                    time.gmtime()
                )
                response.headers["last-modified"] = last_modified
                response.last_modified = last_modified
        
        # Add Vary headers for proper caching
        if "vary" not in response.headers and self.config["vary_headers"]:
            vary_header = ", ".join(self.config["vary_headers"])
            response.headers["vary"] = vary_header
        
        # Add Expires header for older clients
        if ttl > 0:
            expires_time = time.time() + ttl
            expires = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(expires_time))
            response.headers["expires"] = expires
    
    def _is_private_content(self, request: Request, path: str) -> bool:
        """Determine if content is user-specific and should be private."""
        # Check for authentication indicators
        if (request.headers.get("authorization") or 
            request.cookies.get("session_id") or
            request.headers.get("x-api-key")):
            return True
        
        # Check path patterns for private content
        private_patterns = [
            "/api/user/",
            "/api/profile/",
            "/api/account/",
            "/dashboard/",
            "/admin/",
        ]
        
        for pattern in private_patterns:
            if path.startswith(pattern):
                return True
        
        return False
    
    async def _compress_response(self, response: Response) -> Response:
        """Compress response content if appropriate."""
        import gzip
        import io
        
        # Compress the content
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb') as gz_file:
            gz_file.write(response.body or b"")
        
        compressed_content = buffer.getvalue()
        
        # Update response with compressed content
        response.body = compressed_content
        response.headers["content-encoding"] = "gzip"
        response.headers["content-length"] = str(len(compressed_content))
        
        # Remove any existing content-length that might be wrong
        if "content-length" in response.headers:
            del response.headers["content-length"]
        response.headers["content-length"] = str(len(compressed_content))
        
        return response


class StaticFileCacheMiddleware(CacheMiddleware):
    """
    Specialized cache middleware for static files.
    
    Provides aggressive caching for static assets with long TTLs.
    """
    
    def __init__(self, app: Callable, static_url: str = "/static/"):
        # Static files should skip health/metrics endpoints
        skip_paths = ["/health", "/metrics", "/ping", "/api/"]
        super().__init__(app, skip_paths)
        self.static_url = static_url
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with static file caching."""
        # Only apply to static files
        if not request.url.path.startswith(self.static_url):
            return await call_next(request)
        
        response = await call_next(request)
        
        # Add aggressive caching for static files
        if response.status_code == 200 and response.body:
            self._add_static_cache_headers(request, response)
        
        return response
    
    def _add_static_cache_headers(self, request: Request, response: Response) -> None:
        """Add aggressive caching headers for static files."""
        path = request.url.path
        
        # Determine content type from file extension
        content_type = response.headers.get("content-type", "")
        
        # Get TTL for static content
        ttl = get_ttl_for_path(path, is_private=False)
        
        # Add Cache-Control with long TTL
        if ttl > 0:
            cache_control = f"public, max-age={ttl}, immutable"
            response.headers["cache-control"] = cache_control
        
        # Add long expires header
        if ttl > 0:
            expires_time = time.time() + ttl
            expires = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(expires_time))
            response.headers["expires"] = expires


def setup_cache_middleware(app, enable_static_cache: bool = True) -> None:
    """
    Setup cache middleware for FastAPI application.
    
    Args:
        app: FastAPI application instance
        enable_static_cache: Whether to enable specialized static file caching
    """
    # Add general cache middleware
    app.add_middleware(CacheMiddleware)
    
    # Add static file cache middleware if enabled
    if enable_static_cache:
        app.add_middleware(StaticFileCacheMiddleware)




