from fastapi import Header, HTTPException, Request, Depends
from typing import Dict, Optional, AsyncGenerator
import uuid
from .config import Settings
from .service import IntentService
from .rate_limiter import EnhancedRateLimiter, RateLimitConfig
from .core.connections import get_neo4j, get_redis

async def verify_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """
    Verify the API key provided in the request header
    """
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

async def get_rate_limiter(request: Request) -> EnhancedRateLimiter:
    """
    Create and return an enhanced rate limiter instance using the connection pool
    """
    settings = request.app.state.settings
    redis_client = get_redis(request.app)
    
    config = RateLimitConfig(
        window=settings.RATE_LIMIT_WINDOW,
        max_requests=settings.MAX_REQUESTS_PER_WINDOW,
        burst_size=int(settings.MAX_REQUESTS_PER_WINDOW * settings.BURST_MULTIPLIER)
    )
    
    return EnhancedRateLimiter(redis_client, config)

async def check_rate_limit(
    request: Request,
    api_key: str,
    rate_limiter: EnhancedRateLimiter
) -> None:
    """
    Check rate limit for the API key
    """
    print(f"\nChecking rate limit with limiter: {rate_limiter}")
    result = await rate_limiter.check_rate_limit(api_key, request.url.path)
    print(f"Rate limit result: {result}")
    
    if not result["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "reset_time": result["reset_time"],
                "retry_after": result["reset_time"] - request.app.state.settings.RATE_LIMIT_WINDOW
            }
        )

async def get_request_id(
    request_id: Optional[str] = Header(None, alias="X-Request-ID")
) -> str:
    """
    Get or generate request ID for tracing
    """
    if request_id:
        return request_id
    return f"req_{uuid.uuid4().hex[:8]}"

async def get_intent_service(request: Request) -> AsyncGenerator[IntentService, None]:
    """
    Create and return an IntentService instance using the connection pool
    """
    settings = request.app.state.settings
    neo4j_handler = get_neo4j(request.app)
    
    service = IntentService(settings)
    service.set_neo4j_handler(neo4j_handler)   # Set the shared handler
    
    try:
        yield service
    finally:
        # No need to close neo4j_handler as it's managed by the connection manager
        pass

async def get_api_dependencies(
    request: Request,
    request_id: str = Depends(get_request_id),
    api_key: str = Depends(verify_api_key)
) -> Dict:
    """
    Gather all API dependencies with proper connection management
    """
    settings = request.app.state.settings
    rate_limiter = await get_rate_limiter(request)
    await check_rate_limit(request, api_key, rate_limiter)
    
    # Get the first yielded service from the generator
    service = None
    async for svc in get_intent_service(request):
        service = svc
        break
        
    return {
        "request_id": request_id,
        "api_key": api_key,
        "settings": settings,
        "service": service
    }

async def validate_service_health(request: Request) -> None:
    """
    Validate service health before processing requests
    """
    connections = request.app.state.connections
    
    if not connections._initialized:
        raise HTTPException(
            status_code=503,
            detail="Service initializing or unavailable"
        )
    
    # Check Neo4j connection
    try:
        await connections.neo4j_handler.execute_query("RETURN 1", {})
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {str(e)}"
        )
    
    # Check Redis connection
    try:
        await connections.redis_pool.ping()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cache connection error: {str(e)}"
        )