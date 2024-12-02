from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import APIKeyHeader
from .service import ContextService
from typing import Optional
from datetime import datetime
import redis
from .config import get_settings, Settings

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(
    api_key: str = Depends(api_key_header),
    settings: Settings = Depends(get_settings)
) -> str:
    """
    Verify the API key and return the client ID if valid
    """
    # In production, this should check against a secure storage
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )
    
    # For testing purposes, we'll consider "test_api_key" as the only valid key
    if api_key != "test_api_key":
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
        
    return api_key

class RateLimiter:
    """Rate limiting implementation using Redis"""
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        client_id: str,
        limit: int = 100,  # requests per window
        window: int = 60   # window in seconds
    ) -> bool:
        """
        Check if the request is within rate limits
        Returns True if request is allowed, False otherwise
        """
        key = f"rate_limit:{client_id}"
        current = self.redis.get(key)

        if not current:
            self.redis.setex(key, window, 1)
            return True

        current = int(current)
        if current >= limit:
            return False

        self.redis.incr(key)
        return True

async def get_rate_limiter(
    settings: Settings = Depends(get_settings)
) -> RateLimiter:
    """
    Get or create rate limiter instance
    """
    # TODO: Implement proper Redis connection pooling
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    return RateLimiter(redis_client)

async def check_rate_limit(
    request: Request,
    api_key: str = Depends(verify_api_key),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings)
) -> None:
    """
    Check rate limiting for the request
    """
    if not await rate_limiter.check_rate_limit(api_key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )

async def get_request_id(
    x_request_id: Optional[str] = Header(None)
) -> str:
    """
    Get or generate request ID for tracing
    """
    if x_request_id:
        return x_request_id
    return f"req_{datetime.utcnow().timestamp()}"

# Dependency to get service instance
async def get_service(
    settings: Settings = Depends(get_settings)
):
    """
    Get or create service instance with required dependencies
    """
    # This could be enhanced to handle service lifecycle
    from .service import ContextService
    return ContextService(settings)

# Combined dependencies for API endpoints
async def get_api_dependencies(
    request_id: str = Depends(get_request_id),
    api_key: str = Depends(verify_api_key),
    _: None = Depends(check_rate_limit),
    service: "ContextService" = Depends(get_service),
    settings: Settings = Depends(get_settings)
):
    """
    Combine all API dependencies into a single dependency
    """
    return {
        "request_id": request_id,
        "api_key": api_key,
        "service": service,
        "settings": settings
    }