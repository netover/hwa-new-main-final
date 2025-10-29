"""Cache policies and TTL configurations per environment."""

from enum import Enum
from typing import Dict, Any

from resync.config.settings import settings


class CachePolicy(str, Enum):
    """Cache policies for different types of content."""
    
    AGGRESSIVE = "aggressive"  # Long TTL, good for static assets
    MODERATE = "moderate"    # Medium TTL, good for API responses
    CONSERVATIVE = "conservative"  # Short TTL, good for dynamic content
    DISABLED = "disabled"    # No caching


class CacheTTL:
    """Time-to-live values for different content types (in seconds)."""
    
    # Static assets
    CSS = 31536000      # 1 year
    JS = 31536000       # 1 year
    IMAGES = 31536000    # 1 year
    FONTS = 31536000     # 1 year
    VIDEOS = 604800      # 1 week
    
    # API responses
    API_SUCCESS = 300      # 5 minutes
    API_ERROR = 60        # 1 minute
    API_RATE_LIMIT = 60    # 1 minute
    
    # Static pages
    HTML = 3600          # 1 hour
    JSON = 300           # 5 minutes
    
    # Dynamic content
    USER_SPECIFIC = 0     # No cache
    AUTH_REQUIRED = 0      # No cache


class EnvironmentCacheConfig:
    """Cache configuration for different environments."""
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        """Get cache configuration based on current environment."""
        if settings.is_production:
            return EnvironmentCacheConfig._production_config()
        elif settings.is_staging:
            return EnvironmentCacheConfig._staging_config()
        else:
            return EnvironmentCacheConfig._development_config()
    
    @staticmethod
    def _production_config() -> Dict[str, Any]:
        """Production cache configuration - optimized for performance."""
        return {
            "default_ttl": 300,  # 5 minutes
            "max_ttl": 86400,   # 24 hours
            "etag_enabled": True,
            "last_modified_enabled": True,
            "compression_enabled": True,
            "compression_threshold": 1024,  # 1KB
            "vary_headers": ["Accept-Encoding", "Accept-Language"],
            "cache_control_headers": True,
            "public_cache_ttl": {
                "static/css": CacheTTL.CSS,
                "static/js": CacheTTL.JS,
                "static/images": CacheTTL.IMAGES,
                "static/fonts": CacheTTL.FONTS,
                "static/videos": CacheTTL.VIDEOS,
                "api/public": CacheTTL.API_SUCCESS,
                "docs": CacheTTL.HTML,
            },
            "private_cache_ttl": {
                "api/user": CacheTTL.USER_SPECIFIC,
                "api/auth": CacheTTL.AUTH_REQUIRED,
                "api/profile": CacheTTL.USER_SPECIFIC,
            },
            "no_cache_patterns": [
                "/api/auth/",
                "/api/user/profile",
                "/api/sensitive/",
                "/admin/",
            ],
        }
    
    @staticmethod
    def _staging_config() -> Dict[str, Any]:
        """Staging cache configuration - balanced for testing."""
        return {
            "default_ttl": 120,  # 2 minutes
            "max_ttl": 3600,    # 1 hour
            "etag_enabled": True,
            "last_modified_enabled": True,
            "compression_enabled": True,
            "compression_threshold": 512,  # 512 bytes
            "vary_headers": ["Accept-Encoding", "Accept-Language"],
            "cache_control_headers": True,
            "public_cache_ttl": {
                "static/css": CacheTTL.CSS // 4,  # 3 months
                "static/js": CacheTTL.JS // 4,    # 3 months
                "static/images": CacheTTL.IMAGES // 4,  # 3 months
                "static/fonts": CacheTTL.FONTS // 4,   # 3 months
                "static/videos": CacheTTL.VIDEOS,     # 1 week
                "api/public": CacheTTL.API_SUCCESS,     # 5 minutes
                "docs": CacheTTL.HTML,                # 1 hour
            },
            "private_cache_ttl": {
                "api/user": CacheTTL.USER_SPECIFIC,
                "api/auth": CacheTTL.AUTH_REQUIRED,
                "api/profile": CacheTTL.USER_SPECIFIC,
            },
            "no_cache_patterns": [
                "/api/auth/",
                "/api/user/profile",
                "/api/sensitive/",
                "/admin/",
            ],
        }
    
    @staticmethod
    def _development_config() -> Dict[str, Any]:
        """Development cache configuration - minimal for easy debugging."""
        return {
            "default_ttl": 60,   # 1 minute
            "max_ttl": 300,     # 5 minutes
            "etag_enabled": True,
            "last_modified_enabled": True,
            "compression_enabled": False,  # Disable for easier debugging
            "compression_threshold": 1024,
            "vary_headers": ["Accept-Encoding"],
            "cache_control_headers": True,
            "public_cache_ttl": {
                "static/css": CacheTTL.CSS // 52,  # 1 week
                "static/js": CacheTTL.JS // 52,    # 1 week
                "static/images": CacheTTL.IMAGES // 52,  # 1 week
                "static/fonts": CacheTTL.FONTS // 52,   # 1 week
                "static/videos": CacheTTL.VIDEOS,       # 1 week
                "api/public": CacheTTL.API_SUCCESS,     # 5 minutes
                "docs": CacheTTL.HTML,                # 1 hour
            },
            "private_cache_ttl": {
                "api/user": 0,  # No cache in dev
                "api/auth": 0,  # No cache in dev
                "api/profile": 0,  # No cache in dev
            },
            "no_cache_patterns": [
                "/api/",  # Disable all API caching in dev
                "/admin/",
            ],
        }


def get_ttl_for_path(path: str, is_private: bool = False) -> int:
    """Get appropriate TTL for a given path."""
    config = EnvironmentCacheConfig.get_config()
    
    # Check no cache patterns first
    for pattern in config["no_cache_patterns"]:
        if pattern in path:
            return 0
    
    # Select appropriate TTL mapping
    ttl_mapping = config["private_cache_ttl"] if is_private else config["public_cache_ttl"]
    
    # Find matching pattern
    for pattern, ttl in ttl_mapping.items():
        if pattern in path:
            return ttl
    
    # Return default TTL
    return config["default_ttl"]


def should_compress_response(content_length: int, content_type: str) -> bool:
    """Determine if response should be compressed."""
    config = EnvironmentCacheConfig.get_config()
    
    if not config["compression_enabled"]:
        return False
    
    if content_length < config["compression_threshold"]:
        return False
    
    # Compress common text-based content types
    compressible_types = [
        "text/",
        "application/json",
        "application/javascript",
        "application/xml",
        "application/x-javascript",
    ]
    
    return any(content_type.startswith(ct) for ct in compressible_types)


def get_cache_control_header(ttl: int, is_private: bool = False) -> str:
    """Generate Cache-Control header based on TTL and privacy."""
    if ttl == 0:
        return "no-store, no-cache, must-revalidate, max-age=0"
    
    directives = []
    
    if is_private:
        directives.append("private")
    else:
        directives.append("public")
    
    directives.append(f"max-age={ttl}")
    
    if ttl < 300:  # Less than 5 minutes
        directives.append("must-revalidate")
    
    return ", ".join(directives)


def get_etag_header(content: bytes, weak: bool = False) -> str:
    """Generate ETag header for content."""
    import hashlib
    
    # Use MD5 for ETag (fast and sufficient for cache invalidation)
    hash_obj = hashlib.md5(content, usedforsecurity=False)
    etag = hash_obj.hexdigest()
    
    if weak:
        return f'W/"{etag}"'
    else:
        return f'"{etag}"'
