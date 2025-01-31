# Intent Service API Documentation

## API Overview
The Intent Service provides a RESTful API for analyzing and managing user intent patterns. All endpoints require authentication via API key and support rate limiting.

## Authentication
All API requests require an API key passed in the header:
```http
X-API-Key: your_api_key_here
```

## Common Headers
- `X-Request-ID`: Request identifier
- `X-Process-Time`: Processing time in seconds
- `Content-Type: application/json`

## Endpoints

### 1. Analyze Intent Pattern
Analyzes user intent and identifies patterns.

```http
POST /api/v1/intent/analyze
```

#### Request Body
```json
{
    "context_id": "ctx_123",
    "user_id": "user_789",
    "intent_data": {
        "action": "view_product",
        "embedding": [0.1, 0.2, 0.3],
        "confidence": 0.95
    },
    "timestamp": "2024-12-02T10:00:00Z"
}
```

#### Response
```json
{
    "pattern_id": "pat_456",
    "pattern_type": "sequential",
    "confidence": 0.85,
    "related_patterns": ["pat_123", "pat_789"],
    "metadata": {
        "context": {},
        "analysis_info": {}
    },
    "timestamp": "2024-12-02T10:00:00Z"
}
```

### 2. Query Patterns
Query intent patterns with filters.

```http
POST /api/v1/patterns/query
```

#### Request Body
```json
{
    "user_id": "user_789",
    "pattern_type": "sequential",
    "max_depth": 3,
    "min_confidence": 0.7
}
```

#### Response
```json
[
    {
        "pattern_id": "pat_456",
        "pattern_type": "sequential",
        "confidence": 0.85,
        "related_patterns": ["pat_123"],
        "metadata": {}
    }
]
```

### 3. Health Check
Get service health status.

```http
GET /health
```

#### Response
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "connections": {
        "neo4j": "healthy",
        "redis": "healthy"
    },
    "timestamp": "2024-12-02T10:00:00Z"
}
```

### 4. Metrics
Get service metrics in Prometheus format.

```http
GET /metrics
```

## Rate Limiting
- Default window: 60 seconds
- Default limit: 100 requests per window
- Burst multiplier: 2.0

Rate limit headers:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Error Responses

### 1. Rate Limit Exceeded
```json
{
    "detail": {
        "message": "Rate limit exceeded",
        "reset_time": 1640995200,
        "retry_after": 30
    }
}
```

### 2. Authentication Error
```json
{
    "detail": "Invalid API key"
}
```

### 3. Validation Error
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

## Models

### Pattern Types
```python
class PatternType(str, Enum):
    SEQUENTIAL = "sequential"
    TEMPORAL = "temporal"
    BEHAVIORAL = "behavioral"
    COMPOSITE = "composite"
```

### Intent Relationships
```python
class IntentRelationship(str, Enum):
    LEADS_TO = "leads_to"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    DEPENDS_ON = "depends_on"
```

## Best Practices

1. **Request IDs**
   - Always include a `X-Request-ID` header for tracking
   - Use UUID format for request IDs

2. **Error Handling**
   - Implement exponential backoff for rate limits
   - Handle 503 responses during maintenance

3. **Performance**
   - Keep pattern depth ≤ 5 for optimal performance
   - Use batch operations for multiple patterns
   - Implement caching for frequent queries