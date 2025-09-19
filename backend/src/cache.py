"""Redis cache integration for API responses."""

import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import timedelta
import redis.asyncio as redis
from redis.asyncio import Redis
from src.config import settings

logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Base exception for cache operations."""
    pass


class CacheManager:
    """Redis cache manager for API responses and data caching."""
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize cache manager.
        
        Args:
            redis_url: Redis connection URL. Uses config if not provided.
        """
        self.redis_url = redis_url or settings.redis.url
        self.max_connections = settings.redis.max_connections
        self.default_ttl = settings.app.cache_ttl_minutes * 60  # Convert to seconds
        self._redis: Optional[Redis] = None
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._redis.ping()
            logger.info("Successfully connected to Redis cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise CacheError(f"Redis connection failed: {str(e)}")
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            await self._redis.connection_pool.disconnect()
            logger.info("Disconnected from Redis cache")
    
    @property
    def redis(self) -> Redis:
        """Get Redis client instance."""
        if not self._redis:
            raise CacheError("Redis client not connected. Call connect() first.")
        return self._redis
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode cached value for key: {key}")
            await self.delete(key)  # Remove corrupted data
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds or timedelta
            
        Returns:
            True if successful, False otherwise
        """
        try:
            serialized_value = json.dumps(value, default=str)
            
            if ttl is None:
                ttl = self.default_ttl
            elif isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            await self.redis.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False otherwise
        """
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., "flight:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                result = await self.redis.delete(*keys)
                logger.info(f"Deleted {result} keys matching pattern: {pattern}")
                return result
            return 0
        except Exception as e:
            logger.error(f"Cache pattern delete error for pattern {pattern}: {str(e)}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            result = await self.redis.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache exists check error for key {key}: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment, or None if error
        """
        try:
            result = await self.redis.incrby(key, amount)
            return result
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {str(e)}")
            return None
    
    async def set_with_expiry_update(self, key: str, value: Any, ttl: int) -> bool:
        """
        Set value and update expiry if key already exists.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            serialized_value = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Cache set with expiry update error for key {key}: {str(e)}")
            return False
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, or None if key doesn't exist or error
        """
        try:
            ttl = await self.redis.ttl(key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.error(f"Cache TTL check error for key {key}: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform cache health check.
        
        Returns:
            Health status information
        """
        try:
            # Test basic operations
            test_key = "health_check_test"
            test_value = {"timestamp": "test"}
            
            # Set and get test
            await self.set(test_key, test_value, ttl=10)
            retrieved = await self.get(test_key)
            await self.delete(test_key)
            
            if retrieved == test_value:
                info = await self.redis.info()
                return {
                    "status": "healthy",
                    "message": "Redis cache is operational",
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "response_time": "< 10ms"
                }
            else:
                return {
                    "status": "degraded",
                    "message": "Cache operations not working correctly"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Cache health check failed: {str(e)}"
            }


# Cache key builders for consistent key naming
class CacheKeys:
    """Cache key builders for different data types."""
    
    @staticmethod
    def flight_search(origin: str, destination: str, departure_date: str) -> str:
        """Build cache key for flight search results."""
        return f"flight_search:{origin}:{destination}:{departure_date}"
    
    @staticmethod
    def flight_price(flight_id: str) -> str:
        """Build cache key for flight price."""
        return f"flight_price:{flight_id}"
    
    @staticmethod
    def tracking_request(request_id: str) -> str:
        """Build cache key for tracking request."""
        return f"tracking_request:{request_id}"
    
    @staticmethod
    def user_tracking_requests(user_id: str) -> str:
        """Build cache key for user's tracking requests."""
        return f"user_tracking:{user_id}"
    
    @staticmethod
    def price_history(request_id: str) -> str:
        """Build cache key for price history."""
        return f"price_history:{request_id}"
    
    @staticmethod
    def rate_limit(user_id: str, endpoint: str) -> str:
        """Build cache key for rate limiting."""
        return f"rate_limit:{endpoint}:{user_id}"
    
    @staticmethod
    def api_response(endpoint: str, params_hash: str) -> str:
        """Build cache key for API response."""
        return f"api_response:{endpoint}:{params_hash}"


# Global cache manager instance
cache_manager = CacheManager()


# Convenience functions for common operations
async def get_cached_flight_search(
    origin: str, 
    destination: str, 
    departure_date: str
) -> Optional[Dict[str, Any]]:
    """Get cached flight search results."""
    key = CacheKeys.flight_search(origin, destination, departure_date)
    return await cache_manager.get(key)


async def cache_flight_search(
    origin: str, 
    destination: str, 
    departure_date: str, 
    results: Dict[str, Any],
    ttl: Optional[int] = None
) -> bool:
    """Cache flight search results."""
    key = CacheKeys.flight_search(origin, destination, departure_date)
    return await cache_manager.set(key, results, ttl)


async def get_cached_tracking_request(request_id: str) -> Optional[Dict[str, Any]]:
    """Get cached tracking request."""
    key = CacheKeys.tracking_request(request_id)
    return await cache_manager.get(key)


async def cache_tracking_request(
    request_id: str, 
    request_data: Dict[str, Any],
    ttl: Optional[int] = None
) -> bool:
    """Cache tracking request data."""
    key = CacheKeys.tracking_request(request_id)
    return await cache_manager.set(key, request_data, ttl)


async def invalidate_user_cache(user_id: str) -> int:
    """Invalidate all cache entries for a user."""
    pattern = f"*:{user_id}*"
    return await cache_manager.delete_pattern(pattern)


async def invalidate_tracking_cache(request_id: str) -> None:
    """Invalidate cache entries for a specific tracking request."""
    keys_to_delete = [
        CacheKeys.tracking_request(request_id),
        CacheKeys.price_history(request_id)
    ]
    
    for key in keys_to_delete:
        await cache_manager.delete(key)


# Cache decorators for API endpoints
def cache_api_response(ttl: int = None):
    """
    Decorator to cache API responses.
    
    Args:
        ttl: Cache TTL in seconds
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            import hashlib
            cache_key = f"api:{func.__name__}:{hashlib.md5(str(kwargs).encode()).hexdigest()}"
            
            # Try to get from cache first
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator