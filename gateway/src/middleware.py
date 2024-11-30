from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses  import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from typing import Callable
import time
import redis
import os
import logging
from functools import wraps

from .config import settings

logger = logging.getLogger(__name__)

class BaseRateLimiter:
    """Base rate limiter interface."""
    async def check_rate_limit(self, key: str) -> bool:
        raise NotImplementedError

class RedisRateLimiter(BaseRateLimiter):
    """Redis-based rate limiter implementation."""

    def __init__(self):
        try:
            client = redis.Redis(
                host="localhost", 
                port=6379, 
                db=0, 
                decode_responses=True
            )
            client.ping()  # Test connection
            self.redis_client = client
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self.__class__ = MockRateLimiter
            self.__init__()

    async def check_rate_limit(self, key: str) -> bool:
        """Check if request is within rate limits."""
        try:
            current = int(time.time())
            pipe = self.redis_client.pipeline()

            # Add current timestamp and remove expired entries
            pipe.zadd(key, {str(current): current})
            pipe.zremrangebyscore(key, 0, current - 60)
            pipe.zcard(key)
            pipe.expire(key, 60)

            try:
                _, _, request_count, _ = pipe.execute()
                return request_count <= settings.RATE_LIMIT_PER_SECOND
            except redis.RedisError as e:
                logger.warning(f"Redis pipeline error: {e}")
                self.__class__ = MockRateLimiter
                self.__init__()
                return True

        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            self.__class__ = MockRateLimiter
            self.__init__()
            return True


class MockRateLimiter(BaseRateLimiter):
    """Mock rate limiter for testing."""
    async def check_rate_limit(self, key: str) -> bool:
        return True

def get_rate_limiter() -> BaseRateLimiter:
    """Factory function to get appropriate rate limiter."""
    if os.getenv("TESTING", "").lower() == "true":
        return MockRateLimiter()
    return RedisRateLimiter()

_rate_limiter = None

def get_limiter():
    """Singleton accessor for rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = get_rate_limiter()
    return _rate_limiter

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware implementation."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        try:
            limiter = get_limiter()
            client_ip = request.client.host

            # Check rate limit
            try:
                if not await limiter.check_rate_limit(f"rate_limit:{client_ip}"):
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Too many requests"}
                    )
            except Exception as e:
                logger.error(f"Rate limit check failed: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Internal server error"}
                )

            # Process request
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Unhandled error in middleware: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the gateway."""
    try:
        # Reset middleware stack
        app.user_middleware = []
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=settings.CORS_METHODS,
            allow_headers=settings.CORS_HEADERS,
        )
        
        # Add rate limit middleware
        app.add_middleware(RateLimitMiddleware)
        
        # Rebuild middleware stack
        try:
            app.build_middleware_stack()
        except Exception as e:
            logger.error(f"Failed to rebuild middleware stack: {e}")
            # Continue without rebuilding - FastAPI will rebuild on first request
    except Exception as e:
        logger.error(f"Failed to setup middleware: {e}")