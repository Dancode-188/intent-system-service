# Prediction Service API Documentation

## Overview
The Prediction Service API provides endpoints for generating and retrieving predictions based on user behavior patterns and context. This service integrates with the Context and Intent services to provide rich, contextual predictions.

## Base URL
```
http://prediction-service:8002/api/v1
```

## Authentication
All API endpoints require API key authentication using the `X-API-Key` header:

```http
X-API-Key: your_api_key_here
```

## Rate Limiting
The service implements rate limiting with the following default configuration:
- Window size: 60 seconds
- Max requests per window: 100
- Burst size: 200 (configurable via `BURST_MULTIPLIER`)

Rate limit response headers:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1635789600
```

## API Endpoints

### Generate Prediction
Generate a new prediction based on user context and features.

**Endpoint:** `POST /predict`

**Request Body:**
```json
{
    "user_id": "user123",
    "context_id": "ctx_456",
    "prediction_type": "short_term",
    "features": {
        "intent_patterns": ["view_product", "compare_prices"],
        "user_context": {
            "location": "US",
            "device": "mobile"
        }
    }
}
```

**Response:**
```json
{
    "prediction_id": "pred_abc123",
    "predictions": [
        {
            "action": "purchase",
            "probability": 0.85
        },
        {
            "action": "add_to_cart",
            "probability": 0.65
        }
    ],
    "confidence": 0.85,
    "metadata": {
        "model_version": "1.0.0",
        "prediction_type": "short_term",
        "timestamp": "2024-01-31T10:00:00Z",
        "feature_count": 10
    },
    "timestamp": "2024-01-31T10:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Prediction generation failed

### Retrieve Prediction
Retrieve a previously generated prediction by ID.

**Endpoint:** `GET /predictions/{prediction_id}`

**Parameters:**
- `prediction_id` (path): Unique prediction identifier

**Response:**
```json
{
    "prediction_id": "pred_abc123",
    "predictions": [
        {
            "action": "purchase",
            "probability": 0.85
        }
    ],
    "confidence": 0.85,
    "metadata": {
        "model_version": "1.0.0",
        "prediction_type": "short_term",
        "timestamp": "2024-01-31T10:00:00Z"
    },
    "timestamp": "2024-01-31T10:00:00Z"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid API key
- `404 Not Found`: Prediction not found
- `429 Too Many Requests`: Rate limit exceeded

### Health Check
Check service health status.

**Endpoint:** `GET /health`

**Response:**
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "components": {
        "database": "healthy",
        "model": "healthy",
        "cache": "healthy"
    },
    "timestamp": "2024-01-31T10:00:00Z"
}
```

### Metrics
Expose service metrics in Prometheus format.

**Endpoint:** `GET /metrics`

**Response Format:** Prometheus text format
```
# HELP prediction_service_requests_total Total number of HTTP requests
# TYPE prediction_service_requests_total counter
prediction_service_requests_total{method="POST",endpoint="/api/v1/predict",status="success"} 100

# HELP prediction_service_request_duration_seconds HTTP request duration in seconds
# TYPE prediction_service_request_duration_seconds histogram
prediction_service_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/predict",le="0.1"} 95
```

## Request/Response Models

### PredictionRequest
```python
class PredictionRequest(BaseModel):
    """Prediction request model"""
    user_id: str = Field(..., description="Unique user identifier")
    context_id: str = Field(..., description="Context identifier")
    prediction_type: PredictionType = Field(..., description="Type of prediction")
    features: Dict[str, Any] = Field(..., description="Prediction features")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### PredictionResponse
```python
class PredictionResponse(BaseModel):
    """Prediction response model"""
    prediction_id: str
    predictions: List[Dict[str, Any]]
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error messages:

```json
{
    "detail": {
        "message": "Error message here",
        "error_code": "ERROR_CODE",
        "timestamp": "2024-01-31T10:00:00Z",
        "request_id": "req_xyz789"
    }
}
```

Common error codes:
- `VALIDATION_ERROR`: Request validation failed
- `MODEL_ERROR`: ML model processing failed
- `RATE_LIMIT_ERROR`: Rate limit exceeded
- `SERVICE_ERROR`: Internal service error

## Example Usage

### cURL
```bash
# Generate prediction
curl -X POST "http://prediction-service:8002/api/v1/predict" \
     -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
         "user_id": "user123",
         "context_id": "ctx_456",
         "prediction_type": "short_term",
         "features": {
             "intent_patterns": ["view_product"],
             "user_context": {"location": "US"}
         }
     }'

# Retrieve prediction
curl -X GET "http://prediction-service:8002/api/v1/predictions/pred_abc123" \
     -H "X-API-Key: your_api_key"
```

### Python
```python
import httpx

async def generate_prediction(api_key: str, request_data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://prediction-service:8002/api/v1/predict",
            headers={"X-API-Key": api_key},
            json=request_data
        )
        return response.json()
```

## Rate Limiting
The service uses Redis-based rate limiting:

```python
async def check_rate_limit(client_id: str, endpoint: str) -> Dict[str, Any]:
    result = await rate_limiter.check_rate_limit(client_id, endpoint)
    
    if not result["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "reset_time": result["reset_time"],
                "retry_after": result["reset_time"] - result["current_time"]
            }
        )
```

## Additional Headers
All responses include:
- `X-Request-ID`: Unique request identifier
- `X-Process-Time`: Request processing time in seconds

## Best Practices

1. **Error Handling**
   - Always check HTTP status codes
   - Implement exponential backoff for retries
   - Handle rate limiting appropriately

2. **Performance**
   - Keep request payloads small
   - Use connection pooling
   - Cache responses when appropriate

3. **Security**
   - Secure API key storage
   - Use HTTPS in production
   - Validate all input data

## Need Help?
- Check the [Troubleshooting Guide](troubleshooting.md)
- Review [Common Issues](common-issues.md)
- Contact support with your `request_id` for assistance