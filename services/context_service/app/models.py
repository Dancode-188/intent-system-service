from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Any
from datetime import datetime

class ContextRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user123",
                "action": "view_product",
                "context": {
                    "product_id": "prod456",
                    "category": "electronics"
                }
            }
        }
    )
    
    user_id: str
    action: str
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ContextResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "context_id": "ctx_123",
                "embedding": [0.1, 0.2, 0.3],
                "confidence": 0.95,
                "action_type": "exploration",
                "processed_timestamp": "2024-12-02T10:00:00"
            }
        }
    )
    
    context_id: str
    embedding: List[float]
    confidence: float
    action_type: str
    processed_timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2024-12-02T10:00:00"
            }
        }
    )
    
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)