from fastapi import Header, HTTPException, Request, Depends
from fastapi.security import APIKeyHeader
from typing import Dict, Optional, AsyncGenerator
import uuid
import redis.asyncio as redis
from .config import Settings, get_settings
from .service import PredictionService
from .rate_limiter import EnhancedRateLimiter, RateLimitConfig
from .core.connections import get_timescale, get_redis

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(
    api_key: str = Depends(api_key_header),
    settings: Settings = Depends(get_settings)
) -> str:
    """Verify the API key and return it if valid"""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )
    
    # In production, this should check against a secure key store
    if api_key != "test_api_key":
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return api_key

def get_redis_client(request: Request) -> redis.Redis:
    """Get Redis client from app state"""
    return redis.Redis(connection_pool=request.app.state.connections.redis_pool)

# Update get_rate_limiter to use the new function
async def get_rate_limiter(request: Request) -> EnhancedRateLimiter:
    """Create and return a rate limiter instance"""
    settings = request.app.state.settings
    redis_client = get_redis_client(request)
    
    config = RateLimitConfig(
        window=settings.RATE_LIMIT_WINDOW,
        max_requests=settings.MAX_REQUESTS_PER_WINDOW,
        burst_size=int(settings.MAX_REQUESTS_PER_WINDOW * settings.BURST_MULTIPLIER)
    )
    
    return EnhancedRateLimiter(redis_client, config)

async def check_rate_limit(
    request: Request,
    api_key: str = Depends(verify_api_key),
    rate_limiter: EnhancedRateLimiter = Depends(get_rate_limiter)
) -> None:
    """Check rate limit for the API key"""
    result = await rate_limiter.check_rate_limit(api_key, request.url.path)
    
    if not result["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "reset_time": result["reset_time"],
                "retry_after": result["reset_time"] - result["current_time"]
            }
        )

async def get_request_id(
    x_request_id: Optional[str] = Header(None)
) -> str:
    """Get or generate request ID for tracing"""
    if x_request_id:
        return x_request_id
    return f"req_{uuid.uuid4().hex[:8]}"

async def get_prediction_service(
    request: Request
) -> AsyncGenerator[PredictionService, None]:
    """Get or create service instance using the connection pool"""
    settings = request.app.state.settings
    db_handler = get_timescale(request.app)
    
    service = PredictionService(settings)
    service.set_db_handler(db_handler)
    
    try:
        await service.initialize()
        yield service
    finally:
        await service.close()

async def get_api_dependencies(
    request: Request,
    request_id: str = Depends(get_request_id),
    api_key: str = Depends(verify_api_key),
    _: None = Depends(check_rate_limit),
    service: PredictionService = Depends(get_prediction_service)
) -> Dict:
    """Combine all API dependencies"""
    return {
        "request_id": request_id,
        "api_key": api_key,
        "service": service,
        "settings": request.app.state.settings
    }

async def validate_service_health(request: Request) -> None:
    """Validate service health before processing requests"""
    connections = request.app.state.connections
    
    if not connections._initialized:
        raise HTTPException(
            status_code=503,
            detail="Service initializing or unavailable"
        )
    
    # Check TimescaleDB connection
    try:
        await connections.timescale_handler.pool.fetchval('SELECT 1')
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {str(e)}"
        )
    
    # Check Redis connection
    try:
        redis_client = redis.Redis(connection_pool=connections.redis_pool)
        await redis_client.ping()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cache connection error: {str(e)}"
        )