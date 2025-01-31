# Gateway Configuration Guide

## Overview

The API Gateway configuration is managed through environment variables and configuration files, providing flexibility for different deployment environments.

## Environment Variables

### Core Settings
```bash
# Application Settings
APP_NAME="Intent System Gateway"
DEBUG=false
API_V1_PREFIX="/api/v1"

# Security
SECRET_KEY="your-secret-key-here"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_BURST=20

# Service URLs
CONTEXT_SERVICE_URL="http://localhost:8001"
INTENT_SERVICE_URL="http://localhost:8002"
PREDICTION_SERVICE_URL="http://localhost:8003"
REALTIME_SERVICE_URL="http://localhost:8004"

# Redis Configuration
REDIS_HOST="redis"
REDIS_PORT=6379
```

### CORS Configuration
```bash
CORS_ORIGINS="*"
CORS_METHODS="*"
CORS_HEADERS="*"
```

## Configuration Classes

### Main Settings
```python
class Settings(BaseSettings):
    APP_NAME: str
    DEBUG: bool
    API_V1_PREFIX: str
    CORS_ORIGINS: List[str]
    CORS_METHODS: List[str]
    CORS_HEADERS: List[str]
    RATE_LIMIT_PER_SECOND: int
    RATE_LIMIT_BURST: int
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
```

### Circuit Breaker Configuration
```python
class CircuitConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_timeout: int = 30
    failure_window: int = 120
    min_throughput: int = 5
```

## Service Configuration

### Route Definition
```python
class RouteDefinition:
    service_name: str
    path_prefix: str
    methods: List[str]
    strip_prefix: bool = True
    timeout: float = 30.0
    circuit_breaker: bool = True
    rate_limit: bool = True
    auth_required: bool = True
    scopes: List[str]
```

### Service Registry
```python
class ServiceDefinition:
    service_name: str
    instances: Dict[str, ServiceInstance]
    check_endpoint: str = "/health"
    check_interval: int = 30
    metadata: Dict[str, Any]
```

## Middleware Configuration

### Rate Limiting
The rate limiter uses Redis for distributed rate limiting:
```python
class RedisRateLimiter:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
```

### Authentication
JWT configuration:
```python
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/token",
    scopes={
        "read": "Read access",
        "write": "Write access",
        "admin": "Admin access"
    }
)
```

## Docker Configuration

### Docker Compose
```yaml
version: '3.8'

services:
  gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - API_V1_PREFIX=/api/v1
      - SECRET_KEY=your-secret-key
      - RATE_LIMIT_PER_SECOND=10
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY pyproject.toml pytest.ini setup.py ./

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Development Configuration

### pytest Configuration
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = strict
addopts = -v --cov=src --cov-report=term-missing
```

### Coverage Configuration
```toml
[tool.coverage.run]
source = ["src"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "pass",
]
```

## Environment Setup

### Development
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DEBUG=true
export API_V1_PREFIX=/api/v1
export SECRET_KEY=development-key
```

### Production
```bash
# Required environment variables
export DEBUG=false
export SECRET_KEY=your-secure-secret-key
export RATE_LIMIT_PER_SECOND=10
export ACCESS_TOKEN_EXPIRE_MINUTES=30

# Service URLs
export CONTEXT_SERVICE_URL=http://context-service:8001
export INTENT_SERVICE_URL=http://intent-service:8002
export PREDICTION_SERVICE_URL=http://prediction-service:8003
export REALTIME_SERVICE_URL=http://realtime-service:8004
```

## Configuration Best Practices

1. **Security**
   - Never commit sensitive values to version control
   - Use environment variables for secrets
   - Rotate SECRET_KEY regularly

2. **Rate Limiting**
   - Adjust based on service capacity
   - Monitor Redis performance
   - Configure appropriate burst rates

3. **Circuit Breaker**
   - Tune failure thresholds for your use case
   - Adjust recovery timeouts based on service behavior
   - Monitor circuit state changes

4. **Service Discovery**
   - Configure appropriate health check intervals
   - Set realistic timeouts
   - Monitor service health status

5. **Logging**
   - Set appropriate log levels
   - Configure structured logging
   - Implement log rotation