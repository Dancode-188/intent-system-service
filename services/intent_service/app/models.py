from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

class PatternType(str, Enum):
    """
    Types of patterns that can be detected
    """
    SEQUENTIAL = "sequential"
    TEMPORAL = "temporal"
    BEHAVIORAL = "behavioral"
    COMPOSITE = "composite"
    SEQUENCE = "sequence"  # For test compatibility

class IntentRelationship(str, Enum):
    """
    Types of relationships between intents
    """
    LEADS_TO = "leads_to"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    DEPENDS_ON = "depends_on"

class Pattern(BaseModel):
    """
    Pattern model representing a detected behavioral pattern
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "pattern_123",
                "type": "sequential",
                "action": "view_product",
                "attributes": {
                    "category": "product_view",
                    "confidence": 0.95
                }
            }
        }
    )
    
    id: str = Field(..., description="Unique identifier for the pattern")
    type: PatternType = Field(..., description="Type of pattern")
    action: str = Field(..., description="Action or behavior defining the pattern")
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional pattern attributes"
    )

class IntentAnalysisRequest(BaseModel):
    """
    Request model for intent analysis
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "req_123",
                "action": "view product details",
                "pattern_type": "sequential",
                "context": {
                    "user_type": "premium",
                    "session_id": "sess_456"
                },
                "timestamp": "2024-12-02T10:00:00Z"
            }
        }
    )

    request_id: str = Field(..., description="Unique identifier for the request")
    action: str = Field(..., description="Action to analyze")
    pattern_type: Optional[PatternType] = Field(
        None,
        description="Optional type of pattern to look for"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context information for the analysis"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the request"
    )

class IntentAnalysisResponse(BaseModel):
    """
    Response model for intent analysis
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "req_123",
                "primary_intent": "product_view",
                "confidence": 0.95,
                "patterns": [
                    {
                        "pattern_id": "pat_123",
                        "confidence": 0.95,
                        "type": "sequential"
                    }
                ],
                "timestamp": "2024-12-02T10:00:00Z"
            }
        }
    )

    request_id: str = Field(..., description="Request ID from the original request")
    primary_intent: Optional[str] = Field(None, description="Primary identified intent")
    confidence: float = Field(..., description="Confidence score of the analysis")
    patterns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of matching patterns"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )

class IntentPatternRequest(BaseModel):
    """
    Request model for intent pattern analysis
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "context_id": "ctx_123",
                "user_id": "user_789",
                "intent_data": {
                    "action": "view_product",
                    "embedding": [0.1, 0.2, 0.3],
                    "confidence": 0.95
                },
                "timestamp": "2024-12-02T10:00:00Z"
            }
        }
    )
    
    context_id: str
    user_id: str
    intent_data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PatternResponse(BaseModel):
    """
    Response model for identified patterns
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "pat_456",
                "pattern_type": "sequential",
                "confidence": 0.85,
                "related_patterns": ["pat_123", "pat_789"],
                "timestamp": "2024-12-02T10:00:00Z"
            }
        }
    )
    
    pattern_id: str
    pattern_type: PatternType
    confidence: float
    related_patterns: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class GraphQueryRequest(BaseModel):
    """
    Request model for graph queries with validation rules
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_789",
                "pattern_type": "sequential",
                "max_depth": 3,
                "min_confidence": 0.7
            }
        }
    )
    
    user_id: str
    pattern_type: Optional[PatternType] = None
    max_depth: int = Field(default=3, description="Maximum depth for graph traversal")
    min_confidence: float = Field(default=0.7, description="Minimum confidence threshold")

    @field_validator('max_depth')
    @classmethod
    def validate_max_depth(cls, v: int) -> int:
        """
        Validate max_depth is between 1 and 10
        """
        if not isinstance(v, int):
            raise ValueError("max_depth must be an integer")
        if v < 1 or v > 10:
            raise ValueError("max_depth must be between 1 and 10")
        return v

    @field_validator('min_confidence')
    @classmethod
    def validate_min_confidence(cls, v: float) -> float:
        """
        Validate min_confidence is between 0.0 and 1.0
        """
        if not isinstance(v, (int, float)):
            raise ValueError("min_confidence must be a number")
        v = float(v)
        if v < 0.0 or v > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        return v

    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """
        Validate user_id is a non-empty string
        """
        if not isinstance(v, str):
            raise ValueError("user_id must be a string")
        if not v.strip():
            raise ValueError("user_id cannot be empty")
        return v.strip()

    @field_validator('pattern_type')
    @classmethod
    def validate_pattern_type(cls, v: Optional[PatternType]) -> Optional[PatternType]:
        """
        Validate pattern_type is a valid PatternType enum value if provided
        """
        if v is None:
            return v
        if not isinstance(v, PatternType):
            raise ValueError("pattern_type must be a valid PatternType enum value")
        return v

class HealthResponse(BaseModel):
    """
    Health check response model
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2024-12-02T10:00:00Z"
            }
        }
    )
    
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)