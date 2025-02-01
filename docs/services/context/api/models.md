# Context Service API Models

## Overview

This document details the data models used in the Context Service API. All models are implemented using Pydantic for automatic validation and serialization.

## Request Models

### ContextRequest

Main request model for context analysis.

```python
class ContextRequest(BaseModel):
    user_id: str
    action: str
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

#### Fields Description

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | Yes | Unique identifier for the user |
| action | string | Yes | Action being performed |
| context | object | No | Additional context data |
| timestamp | datetime | No | Action timestamp (defaults to now) |

#### Validation Rules
- user_id: Non-empty string
- action: Non-empty string
- context: Optional dictionary of key-value pairs
- timestamp: ISO 8601 formatted datetime

#### Example
```json
{
    "user_id": "user123",
    "action": "view_product",
    "context": {
        "product_id": "prod456",
        "category": "electronics",
        "price": 999.99
    },
    "timestamp": "2024-01-01T10:00:00Z"
}
```

## Response Models

### ContextResponse

Main response model for context analysis results.

```python
class ContextResponse(BaseModel):
    context_id: str
    embedding: List[float]
    confidence: float
    action_type: str
    processed_timestamp: datetime = Field(default_factory=datetime.utcnow)
```

#### Fields Description

| Field | Type | Description |
|-------|------|-------------|
| context_id | string | Unique identifier for analysis result |
| embedding | array[float] | BERT embedding vector (768 dimensions) |
| confidence | float | Confidence score (0-1) |
| action_type | string | Classified action type |
| processed_timestamp | datetime | Processing completion time |

#### Validation Rules
- context_id: Format "ctx_{hash}"
- embedding: List of exactly 768 float values
- confidence: Float between 0 and 1
- action_type: One of ["exploration", "search", "transaction", "other"]
- processed_timestamp: ISO 8601 formatted datetime

#### Example
```json
{
    "context_id": "ctx_abc123",
    "embedding": [0.1, 0.2, ..., 0.1],
    "confidence": 0.95,
    "action_type": "exploration",
    "processed_timestamp": "2024-01-01T10:00:01Z"
}
```

### HealthResponse

Health check endpoint response model.

```python
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

#### Fields Description

| Field | Type | Description |
|-------|------|-------------|
| status | string | Service health status |
| version | string | Service version |
| timestamp | datetime | Health check timestamp |

#### Validation Rules
- status: One of ["healthy", "degraded", "unhealthy"]
- version: Semantic version string
- timestamp: ISO 8601 formatted datetime

#### Example
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "timestamp": "2024-01-01T10:00:00Z"
}
```

## Internal Models

### RateLimitConfig

Configuration for rate limiting.

```python
class RateLimitConfig:
    window: int = 60  # seconds
    max_requests: int = 100
    burst_multiplier: float = 2.0
```

### Error Models

Standard error response format:

```json
{
    "detail": string | {
        "loc": array,
        "msg": string,
        "type": string
    }[]
}
```

#### Validation Error Example
```json
{
    "detail": [
        {
            "loc": ["body", "user_id"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

## Usage Examples

### Creating a Context Request

```python
from datetime import datetime
from app.models import ContextRequest

request = ContextRequest(
    user_id="user123",
    action="view_product",
    context={
        "product_id": "prod456",
        "category": "electronics"
    },
    timestamp=datetime.utcnow()
)
```

### Handling Responses

```python
from app.models import ContextResponse

def process_response(response: ContextResponse):
    if response.confidence > 0.8:
        # High confidence handling
        pass
    else:
        # Low confidence handling
        pass
```

## Schema Evolution

When making changes to these models:

1. Version Changes
   - Major: Breaking changes to model structure
   - Minor: Adding optional fields
   - Patch: Documentation or validation updates

2. Backward Compatibility
   - Always provide defaults for new fields
   - Maintain support for existing clients
   - Document deprecation timelines

3. Migration Guidelines
   - Update API version for breaking changes
   - Provide migration scripts if needed
   - Document upgrade paths