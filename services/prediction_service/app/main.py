from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .models import (
    PredictionRequest,
    PredictionResponse,
    HealthResponse
)
from .service import PredictionService
from .middleware import TimingMiddleware, SecurityHeadersMiddleware
from .dependencies import get_api_dependencies
from .core.connections import ConnectionManager
from .config import Settings, get_settings

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
    
    logger.info("Starting up Prediction Service...")
    yield
    logger.info("Shutting down Prediction Service...")
    
    # Cleanup connections
    await app.state.connections.close()

async def generate_prediction(
    request: PredictionRequest,
    deps: dict = Depends(get_api_dependencies)
):
    """Generate predictions based on request data"""
    try:
        return await deps["service"].process_prediction(request)
    except Exception as e:
        logger.error(f"Error processing prediction: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing prediction: {str(e)}"
        )

async def get_prediction(
    prediction_id: str,
    deps: dict = Depends(get_api_dependencies)
):
    """Retrieve a specific prediction"""
    try:
        prediction = await deps["service"].get_prediction_by_id(prediction_id)
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction {prediction_id} not found"
            )
        return prediction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving prediction: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving prediction: {str(e)}"
        )

async def health_check(deps: dict = Depends(get_api_dependencies)):
    """Health check endpoint"""
    try:
        health_status = await deps["service"].health_check()
        return HealthResponse(
            status=health_status["status"],
            version=deps["settings"].VERSION,
            components=health_status["components"]
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}"
        )

async def metrics():
    """Prometheus metrics endpoint"""
    try:
        return Response(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error generating metrics"
        )

def create_application() -> FastAPI:
    """Create FastAPI application with middleware setup"""
    app = FastAPI(
        title="Prediction Service",
        version=get_settings().VERSION,
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(TimingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.post("/api/v1/predict", response_model=PredictionResponse)(generate_prediction)
    app.get("/api/v1/predictions/{prediction_id}")(get_prediction)
    app.get("/health", response_model=HealthResponse)(health_check)
    app.get("/metrics")(metrics)
    
    return app

# Create application instance
app = create_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)