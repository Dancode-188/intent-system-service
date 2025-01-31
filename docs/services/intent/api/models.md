# Intent Service API Models Documentation

## Model Overview

The Intent Service uses Pydantic models for request/response validation and serialization. All models are defined in `app/models.py`.

## Core Models

### Pattern Type Enumeration
```python
class PatternType(str, Enum):
    """Types of patterns that can be detected"""
    SEQUENTIAL = "sequential"   # Sequential action patterns
    TEMPORAL = "temporal"      # Time-based patterns
    BEHAVIORAL = "behavioral"  # User behavior patterns
    COMPOSITE = "composite"    # Combined pattern types
```

### Intent Relationship Enumeration
```python
class IntentRelationship(str, Enum):
    """Types of relationships between intents"""
    LEADS_TO = "leads_to"     # Sequential relationship
    SIMILAR_TO = "similar_to" # Pattern similarity
    PART_OF = "part_of"      # Component relationship
    DEPENDS_ON = "depends_on" # Dependency relationship
```

### Base Pattern Model
```python
class Pattern(BaseModel):
    """Pattern model representing a detected behavioral pattern"""
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
```

## Request Models

### Intent Analysis Request
```python
class IntentAnalysisRequest(BaseModel):
    """Request model for intent analysis"""
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

    request_id: str
    action: str
    pattern_type: Optional[PatternType] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is not empty"""
        if not v.strip():
            raise ValueError("action cannot be empty")
        return v.strip()
```

### Pattern Query Request
```python
class GraphQueryRequest(BaseModel):
    """Request model for graph queries with validation rules"""
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
        """Validate max_depth is between 1 and 10"""
        if not isinstance(v, int):
            raise ValueError("max_depth must be an integer")
        if v < 1 or v > 10:
            raise ValueError("max_depth must be between 1 and 10")
        return v

    @field_validator('min_confidence')
    @classmethod
    def validate_min_confidence(cls, v: float) -> float:
        """Validate min_confidence is between 0.0 and 1.0"""
        if not isinstance(v, (int, float)):
            raise ValueError("min_confidence must be a number")
        if v < 0.0 or v > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        return float(v)
```

## Response Models

### Intent Analysis Response
```python
class IntentAnalysisResponse(BaseModel):
    """Response model for intent analysis"""
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

    request_id: str
    primary_intent: Optional[str] = None
    confidence: float
    patterns: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern Response
```python
class PatternResponse(BaseModel):
    """Response model for identified patterns"""
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
```

### Health Response
```python
class HealthResponse(BaseModel):
    """Health check response model"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "connections": {
                    "neo4j": "healthy",
                    "redis": "healthy"
                },
                "timestamp": "2024-12-02T10:00:00Z"
            }
        }
    )
    
    status: str
    version: str
    connections: Dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

## Usage Examples

### Creating a Pattern
```python
pattern = Pattern(
    id="pattern_123",
    type=PatternType.SEQUENTIAL,
    action="view_product",
    attributes={
        "category": "product_view",
        "confidence": 0.95
    }
)
```

### Analyzing Intent
```python
request = IntentAnalysisRequest(
    request_id="req_123",
    action="view product details",
    pattern_type=PatternType.SEQUENTIAL,
    context={
        "user_type": "premium",
        "session_id": "sess_456"
    }
)

response = await service.analyze_intent(request)
```

### Querying Patterns
```python
query = GraphQueryRequest(
    user_id="user_789",
    pattern_type=PatternType.SEQUENTIAL,
    max_depth=3,
    min_confidence=0.7
)

patterns = await service.query_patterns(query)
```

## Model Validation

### Custom Validators
```python
@field_validator('user_id')
@classmethod
def validate_user_id(cls, v: str) -> str:
    """Validate user_id is a non-empty string"""
    if not isinstance(v, str):
        raise ValueError("user_id must be a string")
    if not v.strip():
        raise ValueError("user_id cannot be empty")
    return v.strip()
```

### Field Constraints
```python
class ModelWithConstraints(BaseModel):
    required_field: str = Field(..., min_length=1)
    optional_field: Optional[str] = None
    numeric_field: int = Field(gt=0, le=100)
    enum_field: PatternType
```

## Error Handling

### Validation Errors
```python
try:
    request = IntentAnalysisRequest(
        request_id="req_123",
        action=""  # Invalid: empty action
    )
except ValidationError as e:
    print(e.errors())
```

### Response Examples
```json
{
    "detail": [
        {
            "loc": ["body", "action"],
            "msg": "action cannot be empty",
            "type": "value_error"
        }
    ]
}
```