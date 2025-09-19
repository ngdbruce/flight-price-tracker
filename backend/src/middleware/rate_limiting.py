"""Rate limiting middleware for API protection."""

import time
import logging
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.cache import cache_manager, CacheKeys

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis for distributed rate limiting."""
    
    def __init__(self, app, rate_limit: int = None, window_seconds: int = 60):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            rate_limit: Number of requests per window (defaults to config)
            window_seconds: Time window in seconds
        """
        super().__init__(app)
        self.rate_limit = rate_limit or settings.app.api_rate_limit
        self.window_seconds = window_seconds
        
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks and static files
        if self._should_skip_rate_limiting(request):
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        try:
            await self._check_rate_limit(request, client_id)
        except RateLimitExceeded as e:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": e.message,
                    "retry_after": e.retry_after
                },
                headers={"Retry-After": str(e.retry_after)}
            )
        except Exception as e:
            # If rate limiting fails, log error but don't block request
            logger.error(f"Rate limiting error: {e}")
        
        response = await call_next(request)
        return response
    
    def _should_skip_rate_limiting(self, request: Request) -> bool:
        """Check if request should skip rate limiting."""
        skip_paths = [
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static"
        ]
        
        path = request.url.path
        return any(path.startswith(skip_path) for skip_path in skip_paths)
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID from headers (if authenticated)
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
    
    async def _check_rate_limit(self, request: Request, client_id: str):
        """Check if client has exceeded rate limit."""
        endpoint = f"{request.method}:{request.url.path}"
        cache_key = CacheKeys.rate_limit(client_id, endpoint)
        
        try:
            # Get current count
            current_count = await cache_manager.get(cache_key)
            
            if current_count is None:
                # First request in window
                await cache_manager.set(cache_key, 1, ttl=self.window_seconds)
                return
            
            if isinstance(current_count, dict) and "count" in current_count:
                count = current_count["count"]
            else:
                count = current_count
            
            if count >= self.rate_limit:
                # Rate limit exceeded
                ttl = await cache_manager.get_ttl(cache_key)
                retry_after = ttl or self.window_seconds
                
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Maximum {self.rate_limit} requests per {self.window_seconds} seconds.",
                    retry_after
                )
            
            # Increment count
            await cache_manager.increment(cache_key)
            
        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(f"Error checking rate limit for {client_id}: {e}")
            # Don't block request if rate limiting fails


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting with different limits for different endpoints."""
    
    def __init__(self, app):
        super().__init__(app)
        # Define rate limits per endpoint pattern
        self.endpoint_limits = {
            "GET:/api/v1/flights/search": {"limit": 60, "window": 60},  # 1 per second
            "POST:/api/v1/tracking/requests": {"limit": 20, "window": 60},  # 20 per minute
            "GET:/api/v1/tracking/requests": {"limit": 100, "window": 60},  # 100 per minute
            "default": {"limit": settings.app.api_rate_limit, "window": 60}
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request with advanced rate limiting."""
        if self._should_skip_rate_limiting(request):
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        endpoint = f"{request.method}:{request.url.path}"
        
        # Get rate limit config for this endpoint
        limit_config = self.endpoint_limits.get(endpoint, self.endpoint_limits["default"])
        
        try:
            await self._check_rate_limit(
                client_id, 
                endpoint, 
                limit_config["limit"], 
                limit_config["window"]
            )
        except RateLimitExceeded as e:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": e.message,
                    "retry_after": e.retry_after,
                    "endpoint": endpoint,
                    "limit": limit_config["limit"],
                    "window": limit_config["window"]
                },
                headers={"Retry-After": str(e.retry_after)}
            )
        except Exception as e:
            logger.error(f"Advanced rate limiting error: {e}")
        
        response = await call_next(request)
        
        # Add rate limit headers to successful responses
        await self._add_rate_limit_headers(response, client_id, endpoint, limit_config)
        
        return response
    
    def _should_skip_rate_limiting(self, request: Request) -> bool:
        """Check if request should skip rate limiting."""
        skip_paths = [
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/static",
            "/"
        ]
        
        path = request.url.path
        return any(path.startswith(skip_path) for skip_path in skip_paths)
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Priority: API key -> User ID -> IP address
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"
        
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"
        
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
    
    async def _check_rate_limit(
        self, 
        client_id: str, 
        endpoint: str, 
        limit: int, 
        window: int
    ):
        """Check if client has exceeded rate limit for specific endpoint."""
        cache_key = CacheKeys.rate_limit(client_id, endpoint)
        
        try:
            # Use sliding window approach
            now = int(time.time())
            window_start = now - window
            
            # Get current requests in window
            requests_data = await cache_manager.get(cache_key)
            
            if requests_data is None:
                requests_data = {"requests": [], "count": 0}
            
            # Filter requests within current window
            if isinstance(requests_data, dict) and "requests" in requests_data:
                recent_requests = [
                    req_time for req_time in requests_data["requests"] 
                    if req_time > window_start
                ]
            else:
                # Fallback for simple count
                if requests_data >= limit:
                    ttl = await cache_manager.get_ttl(cache_key)
                    raise RateLimitExceeded(
                        f"Rate limit exceeded. Maximum {limit} requests per {window} seconds.",
                        ttl or window
                    )
                await cache_manager.increment(cache_key)
                return
            
            if len(recent_requests) >= limit:
                # Rate limit exceeded
                oldest_request = min(recent_requests) if recent_requests else now
                retry_after = window - (now - oldest_request)
                
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Maximum {limit} requests per {window} seconds.",
                    max(retry_after, 1)
                )
            
            # Add current request
            recent_requests.append(now)
            
            # Update cache
            updated_data = {
                "requests": recent_requests[-limit:],  # Keep only last 'limit' requests
                "count": len(recent_requests)
            }
            await cache_manager.set(cache_key, updated_data, ttl=window)
            
        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(f"Error in advanced rate limiting for {client_id} on {endpoint}: {e}")
    
    async def _add_rate_limit_headers(
        self, 
        response, 
        client_id: str, 
        endpoint: str, 
        limit_config: Dict
    ):
        """Add rate limit headers to response."""
        try:
            cache_key = CacheKeys.rate_limit(client_id, endpoint)
            requests_data = await cache_manager.get(cache_key)
            
            if requests_data and isinstance(requests_data, dict):
                remaining = max(0, limit_config["limit"] - requests_data.get("count", 0))
                response.headers["X-RateLimit-Limit"] = str(limit_config["limit"])
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Window"] = str(limit_config["window"])
        except Exception as e:
            logger.error(f"Error adding rate limit headers: {e}")


# Rate limiting utilities
async def get_rate_limit_status(client_id: str, endpoint: str) -> Dict:
    """Get current rate limit status for a client and endpoint."""
    cache_key = CacheKeys.rate_limit(client_id, endpoint)
    
    try:
        requests_data = await cache_manager.get(cache_key)
        ttl = await cache_manager.get_ttl(cache_key)
        
        if requests_data is None:
            return {
                "requests_made": 0,
                "limit": settings.app.api_rate_limit,
                "remaining": settings.app.api_rate_limit,
                "reset_time": None
            }
        
        if isinstance(requests_data, dict):
            count = requests_data.get("count", 0)
        else:
            count = requests_data
        
        return {
            "requests_made": count,
            "limit": settings.app.api_rate_limit,
            "remaining": max(0, settings.app.api_rate_limit - count),
            "reset_time": ttl
        }
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        return {
            "requests_made": 0,
            "limit": settings.app.api_rate_limit,
            "remaining": settings.app.api_rate_limit,
            "reset_time": None,
            "error": str(e)
        }


async def reset_rate_limit(client_id: str, endpoint: Optional[str] = None):
    """Reset rate limit for a client."""
    try:
        if endpoint:
            cache_key = CacheKeys.rate_limit(client_id, endpoint)
            await cache_manager.delete(cache_key)
        else:
            # Reset all rate limits for client
            pattern = f"rate_limit:*:{client_id}"
            await cache_manager.delete_pattern(pattern)
        
        logger.info(f"Rate limit reset for client {client_id} on endpoint {endpoint or 'all'}")
    except Exception as e:
        logger.error(f"Error resetting rate limit: {e}")
        raise