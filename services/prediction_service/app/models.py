from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class PredictionType(str, Enum):
    """Types of predictions"""
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"

class PredictionRequest(BaseModel):
    """Prediction request model"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user123",
                "context_id": "ctx_456",
                "prediction_type": "short_term",
                "features": {
                    "intent_patterns": ["pattern1", "pattern2"],
                    "user_context": {"location": "US", "device": "mobile"}
                }
            }
        }
    )

    user_id: str = Field(..., description="Unique user identifier")
    context_id: str = Field(..., description="Context identifier")
    prediction_type: PredictionType = Field(..., description="Type of prediction")
    features: Dict[str, Any] = Field(..., description="Prediction features")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PredictionResponse(BaseModel):
    """Prediction response model"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prediction_id": "pred_789",
                "predictions": [
                    {"action": "purchase", "probability": 0.85},
                    {"action": "compare", "probability": 0.65}
                ],
                "confidence": 0.85,
                "timestamp": "2024-12-28T10:00:00Z"
            }
        }
    )

    prediction_id: str
    predictions: List[Dict[str, Any]]  # Changed from Dict[str, float] to Dict[str, Any]
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthResponse(BaseModel):
    """Health check response model"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "components": {
                    "database": "healthy",
                    "model": "healthy"
                }
            }
        }
    )

    status: str
    version: str
    components: Dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)