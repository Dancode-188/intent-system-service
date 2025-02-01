# Context Service API Documentation

## API Overview

The Context Service provides REST endpoints for real-time context analysis and embedding generation. All endpoints are prefixed with `/api/v1`.

## Authentication

All endpoints require API key authentication via the `X-API-Key` header.

## Endpoints

### 1. Analyze Context

Analyzes user context and generates embeddings.

```
POST /api/v1/context
```

#### Request Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| X-API-Key | string | Yes | API authentication key |
| X-Request-ID | string | No | Custom request identifier |

#### Request Body

```json
{
    "user_id": "string",
    "action": "string",
    "context": {
        "key1": "value1",
        "key2": "value2"
    },
    "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | Yes | Unique identifier for the user |
| action | string | Yes | User action being analyzed |
| context | object | No | Additional context information |
| timestamp | string (ISO 8601) | No | Time of action (defaults to current time) |

#### Response Body

```json
{
    "context_id": "ctx_abc123",
    "embedding": [0.1, 0.2, ...],
    "confidence": 0.95,
    "action_type": "exploration",
    "processed_timestamp": "2024-01-01T00:00:01Z"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| context_id | string | Unique identifier for the context analysis |
| embedding | array[float] | 768-dimensional context embedding |
| confidence | float | Confidence score (0-1) |
| action_type | string | Classified action type |
| processed_timestamp | string | Processing completion time |

#### Action Types

- `exploration`: Browsing or viewing actions
- `search`: Search-related actions
- `transaction`: Purchase or conversion actions
- `other`: Unclassified actions

#### Example Request

```bash
curl -X POST "http://api.example.com/api/v1/context" \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
         "user_id": "user123",
         "action": "view_product",
         "context": {
             "product_id": "prod456",
             "category": "electronics",
             "price": 999.99
         }
     }'
```

#### Example Response

```json
{
    "context_id": "ctx_abc123",
    "embedding": [0.1, 0.2, 0.3, ...],
    "confidence": 0.95,
    "action_type": "exploration",
    "processed_timestamp": "2024-01-01T00:00:01Z"
}
```

### 2. Health Check

Check service health status.

```
GET /health
```

#### Response Body

```json
{
    "status": "healthy",
    "version": "0.1.0",
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### 3. Metrics

Expose service metrics for monitoring.

```
GET /metrics
```

#### Response Body

```json
{
    "requests_total": 1000,
    "requests_failed": 5,
    "average_processing_time": 0.095
}
```

## Rate Limiting

- Default limit: 100 requests per minute per API key
- Burst limit: 200 requests per minute
- Rate limit headers included in responses

## Error Responses

### 401 Unauthorized

```json
{
    "detail": "Invalid API key"
}
```

### 403 Forbidden

```json
{
    "detail": "API key is required"
}
```

### 422 Validation Error

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

### 429 Too Many Requests

```json
{
    "detail": "Rate limit exceeded"
}
```

### 500 Internal Server Error

```json
{
    "detail": "Error processing context: {error_message}"
}
```

## Best Practices

1. **Request IDs**
   - Always provide a unique X-Request-ID for tracing
   - Store the ID for correlation with responses

2. **Error Handling**
   - Implement exponential backoff for rate limits
   - Handle all error responses appropriately
   - Log failed request details for debugging

3. **Performance**
   - Batch requests when possible
   - Cache embeddings for frequently used contexts
   - Monitor response times for optimization

4. **Security**
   - Rotate API keys regularly
   - Use HTTPS for all requests
   - Validate and sanitize all inputs