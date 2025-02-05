import redis.asyncio as redis
from datetime import datetime
import json
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class RateLimitConfig:
    """Rate limit configuration"""
    def __init__(
        self,
        window: int = 60,
        max_requests: int = 100,
        burst_size: Optional[int] = None
    ):
        self.window = window
        self.max_requests = max_requests
        self.burst_size = burst_size or max_requests * 2

class EnhancedRateLimiter:
    """
    Enhanced rate limiter with Redis backend and burst handling
    """
    def __init__(
        self,
        redis_client: redis.Redis,
        config: RateLimitConfig
    ):
        self.redis = redis_client
        self.config = config

    async def check_rate_limit(
        self,
        client_id: str,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Check rate limit with detailed response
        """
        key = f"rate_limit:{client_id}:{endpoint}"
        now = datetime.utcnow().timestamp()
        window_start = int(now - self.config.window)

        try:
            # Use Redis pipeline for atomic operations
            async with self.redis.pipeline() as pipe:
                # Clean old requests
                await pipe.zremrangebyscore(key, 0, window_start)
                # Count requests in current window
                await pipe.zcard(key)
                # Add current request
                await pipe.zadd(key, {str(now): now})
                # Set expiry on the key
                await pipe.expire(key, self.config.window * 2)
                # Execute pipeline
                _, request_count, _, _ = await pipe.execute()

            # Calculate remaining requests
            remaining = self.config.max_requests - request_count
            
            # Check if within burst limit
            is_allowed = request_count <= self.config.burst_size
            
            return {
                "allowed": is_allowed,
                "current_requests": request_count,
                "remaining_requests": max(0, remaining),
                "reset_time": int(now) + self.config.window,
                "burst_remaining": max(0, self.config.burst_size - request_count)
            }

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # Fail open - allow request but log error
            return {
                "allowed": True,
                "current_requests": 0,
                "remaining_requests": self.config.max_requests,
                "reset_time": int(now) + self.config.window,
                "burst_remaining": self.config.burst_size,
                "error": "Rate limiting temporarily unavailable"
            }

    async def record_usage(
        self,
        client_id: str,
        endpoint: str,
        usage_data: Dict[str, Any]
    ) -> None:
        """
        Record detailed usage data for analytics
        """
        usage_key = f"usage:{client_id}:{endpoint}:{datetime.utcnow().date().isoformat()}"
        try:
            await self.redis.hset(
                usage_key,
                datetime.utcnow().isoformat(),
                json.dumps(usage_data)
            )
            await self.redis.expire(usage_key, 86400)  # 24 hours
        except redis.RedisError as e:
            logger.error(f"Failed to record usage data: {e}")

    async def get_usage_analytics(
        self,
        client_id: str,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get usage analytics for a client
        """
        pattern = f"usage:{client_id}:*"
        if endpoint:
            pattern = f"usage:{client_id}:{endpoint}:*"
            
        try:
            keys = await self.redis.keys(pattern)
            analytics = {}
            
            for key in keys:
                usage_data = await self.redis.hgetall(key)
                analytics[key] = {
                    k: json.loads(v) for k, v in usage_data.items()
                }
                
            return analytics
        except redis.RedisError as e:
            logger.error(f"Failed to get usage analytics: {e}")
            return {}
        
    async def close(self):
        """Close the rate limiter and cleanup resources"""
        try:
            if hasattr(self, 'redis'):
                await self.redis.close()
        except Exception as e:
            logger.error(f"Error closing rate limiter: {e}")