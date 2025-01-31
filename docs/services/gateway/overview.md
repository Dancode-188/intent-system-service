# API Gateway Service

## Overview

The ISaaS API Gateway serves as the central entry point for all system services, providing robust request routing, authentication, rate limiting, and circuit breaker functionality. Built with FastAPI, it implements a sophisticated service discovery mechanism and privacy-preserving request handling.

## Key Features

### Core Functionality
- Dynamic service discovery and registration
- Request routing with circuit breaker protection
- Redis-based rate limiting
- JWT authentication with scope-based authorization
- Health checking and service monitoring
- Privacy header validation
- Comprehensive error handling

### Technical Implementation
- FastAPI framework with high-performance Uvicorn server
- Redis for rate limiting and caching
- Circuit breaker pattern for fault tolerance
- Service registry for dynamic service discovery
- Docker containerization support

## Service Architecture

### Service Discovery
```python
# Service registration example
registration = RegistrationRequest(
    service_name="context_service",
    host="context-service",
    port=8001,
    check_endpoint="/health",
    check_interval=30
)
```

The following diagram illustrates the service discovery and health checking process:
```mermaid
sequenceDiagram
    participant S as Service
    participant R as Registry
    participant H as Health Checker
    participant G as Gateway
    participant C as Client

    S->>R: Register Service
    R->>H: Start Health Checking
    
    loop Every Check Interval
        H->>S: Health Check
        S->>H: Health Status
        H->>R: Update Status
    end

    C->>G: Request
    G->>R: Get Healthy Instance
    R->>G: Return Instance
    G->>S: Forward Request
    S->>G: Response
    G->>C: Return Response
```

### Circuit Breaker
The gateway implements a sophisticated circuit breaker pattern to protect services from cascading failures. For configuration details, see the [Configuration Guide](configuration.md#circuit-breaker-configuration). For troubleshooting circuit breaker issues, refer to the [Troubleshooting Guide](troubleshooting.md#circuit-breaker-issues).

The following diagram illustrates the circuit breaker state machine:
```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initialize
    
    CLOSED --> OPEN: Failure Threshold Exceeded
    note right of OPEN
        - Fails Fast
        - No Requests Forwarded
        - Recovery Timer Started
    end note
    
    OPEN --> HALF_OPEN: Recovery Timeout
    note right of HALF_OPEN
        - Limited Requests
        - Success Counting
        - Monitoring Recovery
    end note
    
    HALF_OPEN --> CLOSED: Consecutive Successes
    HALF_OPEN --> OPEN: Single Failure
    
    CLOSED --> CLOSED: Successful Request
    note left of CLOSED
        - Normal Operation
        - All Requests Forwarded
        - Failure Counting
    end note
```



### Rate Limiting
Redis-based rate limiting with configurable thresholds:
- Default: 10 requests per second
- Burst capacity: 20 requests
- Fallback to mock limiter if Redis unavailable

## Authentication

```mermaid
sequenceDiagram
    participant C as Client
    participant G as Gateway
    participant A as Auth Service
    participant S as Service

    C->>G: Request with Credentials
    G->>A: Validate Credentials
    A->>G: Return JWT Token
    G->>C: Return Token

    Note over C,G: Subsequent Requests

    C->>G: Request with JWT
    G->>G: Validate Token
    G->>G: Check Scopes
    G->>S: Forward Request
    S->>G: Response
    G->>C: Return Response
```

### JWT Authentication
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Supported scopes:
- `read`: Read access to resources
- `write`: Write access to resources
- `admin`: Administrative access

### Token Endpoints
- `POST /api/v1/auth/token`: Obtain access token
- `GET /api/v1/users/me`: Get current user info

## Core Services

### Context Service
- Prefix: `/api/v1/context`
- Methods: GET, POST
- Authentication: Required
- Circuit Breaker: Enabled
- Rate Limiting: Enabled

### Intent Service
- Prefix: `/api/v1/intent`
- Methods: GET, POST
- Authentication: Required
- Circuit Breaker: Enabled
- Rate Limiting: Enabled

### Prediction Service
- Prefix: `/api/v1/predict`
- Methods: GET, POST
- Authentication: Required
- Circuit Breaker: Enabled
- Rate Limiting: Enabled

### Realtime Service
- Prefix: `/api/v1/realtime`
- Methods: GET, POST, WEBSOCKET
- Authentication: Required
- Circuit Breaker: Disabled
- Rate Limiting: Enabled

## Error Handling

Standard error response format:
```json
{
    "error": {
        "code": "string",
        "message": "string",
        "details": {}
    },
    "request_id": "string"
}
```

Common error types:
- `AUTH_ERROR`: Authentication failures
- `RATE_LIMIT`: Rate limit exceeded
- `CIRCUIT_OPEN`: Circuit breaker is open
- `SERVICE_UNAVAILABLE`: Service health check failed
- `INVALID_REQUEST`: Invalid request parameters

## Deployment

### Docker Deployment
```yaml
services:
  gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - API_V1_PREFIX=/api/v1
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
```

### Environment Variables
- `DEBUG`: Enable debug mode
- `API_V1_PREFIX`: API version prefix
- `SECRET_KEY`: JWT secret key
- `RATE_LIMIT_PER_SECOND`: Rate limit threshold
- `*_SERVICE_URL`: Service endpoint URLs
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration
- `REDIS_HOST/REDIS_PORT`: Redis connection

## Health Monitoring

### Health Check Endpoint
```http
GET /health
```

Response:
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-01-31T12:00:00Z"
}
```

### Service Health Checks
- Periodic health checks for all registered services
- Configurable check intervals
- Automatic service status updates

## Development Setup

### Prerequisites
- Python 3.11+
- Redis 6.0+
- Docker & Docker Compose

### Local Development
1. Clone repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start Redis:
   ```bash
   docker-compose up redis
   ```
4. Run gateway:
   ```bash
   uvicorn src.main:app --reload
   ```

## Testing
```bash
# Run tests with coverage
pytest --cov=src --cov-report=term-missing
```

## Performance Considerations

### Optimization Features
- Redis-based rate limiting
- Circuit breaker pattern
- Service health monitoring
- Request timeout handling

### Resource Requirements
- Minimum 2 CPU cores
- 4GB RAM
- Redis instance for rate limiting