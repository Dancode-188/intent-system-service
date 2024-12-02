from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import ContextRequest, ContextResponse, HealthResponse
from .config import get_settings, Settings
from .dependencies import get_api_dependencies
from datetime import datetime
from typing import Dict

# Create FastAPI application
app = FastAPI(title="Context Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/context", response_model=ContextResponse)
async def analyze_context(
    request: ContextRequest,
    deps: Dict = Depends(get_api_dependencies)
):
    """
    Analyze user context and generate embedding
    """
    try:
        return await deps["service"].process_context(request)
    except Exception as e:
        # Log the error here if needed
        raise HTTPException(
            status_code=500,
            detail=f"Error processing context: {str(e)}"
        ) from e

@app.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)):
    """
    Health check endpoint
    """
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.utcnow()
    )

@app.get("/metrics")
async def metrics():
    """
    Expose metrics for monitoring
    """
    # TODO: Implement metrics collection and exposure
    return {
        "requests_total": 0,
        "requests_failed": 0,
        "average_processing_time": 0
    }