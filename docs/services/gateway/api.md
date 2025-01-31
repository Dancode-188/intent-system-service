# API Gateway Endpoints Reference

## Core Endpoints

### Health Check
```http
GET /health
```

Returns gateway health status.

**Response**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-01-31T12:00:00Z"
}
```

### OpenAPI Documentation
```http
GET /docs
```
Swagger UI documentation interface.

```http
GET /openapi.json
```
OpenAPI specification in JSON format.

## Authentication

### Token Generation
```http
POST /api/v1/auth/token
```

OAuth2 compatible token endpoint.

**Request Body** (form-data)
```
username: string
password: string
scope: string (optional)
```

**Response**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

**Error Responses**
- `401` Invalid credentials
- `400` Invalid request format

### Current User
```http
GET /api/v1/users/me
```

Get current authenticated user information.

**Headers**
```
Authorization: Bearer <token>
```

**Response**
```json
{
    "username": "string",
    "email": "user@example.com",
    "full_name": "string",
    "disabled": false,
    "scopes": ["read", "write"]
}
```

## Service Routes

### Context Service
```http
POST /api/v1/context/analyze
GET /api/v1/context/status/{job_id}
```

**Required Headers**
```http
Authorization: Bearer <token>
Content-Type: application/json
```

**Optional Headers**
```http
X-Request-ID: <request_id>
X-Correlation-ID: <correlation_id>
```

### Intent Service
```http
POST /api/v1/intent/process
GET /api/v1/intent/patterns/{user_id}
```

**Required Headers**
```http
Authorization: Bearer <token>
Content-Type: application/json
```

### Prediction Service
```http
POST /api/v1/predictions/generate
GET /api/v1/predictions/status/{prediction_id}
```

**Required Headers**
```http
Authorization: Bearer <token>
Content-Type: application/json
```

## Request/Response Formats

### Standard Error Response
```json
{
    "error": {
        "code": "string",
        "message": "string",
        "details": {
            "additional": "information"
        }
    },
    "request_id": "string"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `AUTH_ERROR` | Authentication failure |
| `RATE_LIMIT` | Rate limit exceeded |
| `CIRCUIT_OPEN` | Circuit breaker is open |
| `SERVICE_UNAVAILABLE` | Service health check failed |
| `INVALID_REQUEST` | Invalid request parameters |

## Headers

### Required Headers
- `Authorization`: Bearer token for authenticated endpoints
- `Content-Type`: Application/JSON for POST/PUT requests

### Response Headers
- `X-Request-ID`: Request identifier
- `X-RateLimit-Limit`: Rate limit ceiling
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Rate limit reset time

## Rate Limiting

Rate limits are applied per IP address and authenticated user:

| Scope | Limit |
|-------|-------|
| Default | 10 req/sec |
| Burst | 20 req/sec |
| Authenticated | 20 req/sec |

Rate limit headers are included in all responses:
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1635959345
```

## Circuit Breaker

Services protected by circuit breaker will return:
```json
{
    "error": {
        "code": "CIRCUIT_OPEN",
        "message": "Service temporarily unavailable",
        "details": {
            "service": "service_name",
            "retry_after": "2024-01-31T12:05:00Z"
        }
    }
}
```

## Service Discovery

Services are automatically discovered and health-checked. A service becomes unavailable when health checks fail, resulting in:
```json
{
    "error": {
        "code": "SERVICE_UNAVAILABLE",
        "message": "Service is not healthy",
        "details": {
            "service": "service_name",
            "last_check": "2024-01-31T12:00:00Z"
        }
    }
}
```

## Websocket Support

### Real-time Updates
```http
WS /api/v1/realtime
```

**Query Parameters**
- `token`: Bearer token for authentication
- `channels`: Comma-separated list of channels to subscribe to

**Message Format**
```json
{
    "type": "message_type",
    "data": {},
    "timestamp": "2024-01-31T12:00:00Z"
}
```

## API Versioning

All endpoints are versioned using URL prefixing:
- Current version: `/api/v1/`
- Beta features: `/api/v1-beta/`

## CORS Support

The API supports CORS with configurable:
- Origins
- Methods
- Headers
- Credentials

Default configuration allows all origins (`*`) for development.