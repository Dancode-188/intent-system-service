from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import logging
import json
from datetime import datetime

from app.service import IntentService
from app.middleware import TimingMiddleware, SecurityHeadersMiddleware
from app.dependencies import (
    verify_api_key,
    get_rate_limiter,
    check_rate_limit,
    get_request_id,
    get_intent_service,
    get_api_dependencies,
    validate_service_health
)
from app.models import (
    IntentPatternRequest, 
    PatternResponse, 
    GraphQueryRequest,
    HealthResponse
)
from app.config import Settings, get_settings
from app.core.connections import ConnectionManager

# Configure logging
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    settings = get_settings()
    
    # Initialize connection manager
    app.state.connections = ConnectionManager(settings)
    await app.state.connections.init()
    
    # Store settings in app state
    app.state.settings = settings
    
    logger.info("Starting up Intent Service...")
    yield
    logger.info("Shutting down Intent Service...")
    
    # Cleanup connections
    await app.state.connections.close()

def create_application() -> FastAPI:
    """Create FastAPI application with proper middleware setup"""
    app = FastAPI(
        title="Intent Service",
        version=get_settings().VERSION,
        lifespan=lifespan
    )
    
    # Add middleware in correct order
    app.add_middleware(TimingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app

# Create application instance
app = create_application()

@app.get("/health", response_model=HealthResponse, dependencies=[Depends(verify_api_key)])
async def health_check(
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """Enhanced health check endpoint with connection status"""
    await validate_service_health(request)
    
    try:
        connections = request.app.state.connections
        status = "healthy" if connections._initialized else "degraded"
        
        response = HealthResponse(
            status=status,
            version=request.app.state.settings.VERSION,
            connections={
                "neo4j": "healthy" if connections.neo4j_handler else "unavailable",
                "redis": "healthy" if connections.redis_pool else "unavailable"
            }
        )
        
        return response
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="degraded",
            version=request.app.state.settings.VERSION,
            error=str(e)
        )

@app.get("/metrics", dependencies=[Depends(verify_api_key)])
async def metrics():
    """Prometheus metrics endpoint"""
    try:
        return Response(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error generating metrics"
        )

@app.post("/api/v1/intent/analyze", response_model=PatternResponse)
async def analyze_intent(
    request: IntentPatternRequest,
    dependencies: dict = Depends(get_api_dependencies)
):
    """Analyze user intent pattern and update intent graph."""
    try:
        service = dependencies["service"]
        result = await service.analyze_intent_pattern(
            request.user_id,
            request.intent_data
        )
        return PatternResponse(**result)
    except Exception as e:
        logger.error(f"Intent analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/patterns/query", response_model=list[PatternResponse])
async def query_patterns(
    request: GraphQueryRequest,
    dependencies: dict = Depends(get_api_dependencies)
):
    """Query intent patterns with privacy-preserving filters."""
    try:
        service = dependencies["service"]
        patterns = await service.query_patterns(
            user_id=request.user_id,
            pattern_type=request.pattern_type,
            max_depth=request.max_depth,
            min_confidence=request.min_confidence
        )
        return [PatternResponse(**pattern) for pattern in patterns]
    except Exception as e:
        logger.error(f"Pattern query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return Response(
        status_code=exc.status_code,
        content=json.dumps({
            "detail": exc.detail,
            "request_id": request.state.request_id,
            "timestamp": datetime.utcnow().isoformat()
        }),
        media_type="application/json"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)