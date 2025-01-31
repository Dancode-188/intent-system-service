# Prediction Service Configuration Guide

## Overview
This guide covers the configuration options for the Prediction Service, including environment variables, database settings, service integrations, and performance tuning.

## Environment Variables

### Core Settings
```env
# Service Information
PREDICTION_SERVICE_NAME=prediction-service
PREDICTION_VERSION=0.1.0
PREDICTION_DEBUG=false

# API Configuration
PREDICTION_API_PREFIX=/api/v1

# ML Model Configuration
PREDICTION_MODEL_PATH=/app/models
PREDICTION_CONFIDENCE_THRESHOLD=0.7
PREDICTION_MAX_PREDICTIONS=10

# Service Integration URLs
PREDICTION_CONTEXT_SERVICE_URL=http://context-service:8000
PREDICTION_INTENT_SERVICE_URL=http://intent-service:8000
```

### Database Configuration
```env
# TimescaleDB Connection
PREDICTION_TIMESCALE_URL=postgresql://prediction_user:prediction_pass@timescaledb:5432/prediction_db
PREDICTION_TIMESCALE_POOL_SIZE=20

# Redis Configuration
PREDICTION_REDIS_URL=redis://redis:6379/0
PREDICTION_REDIS_POOL_SIZE=20
```

### Rate Limiting
```env
# Rate Limiting Settings
PREDICTION_RATE_LIMIT_WINDOW=60
PREDICTION_MAX_REQUESTS_PER_WINDOW=100
PREDICTION_BURST_MULTIPLIER=2.0
```

### Privacy Settings
```env
# Privacy Configuration
PREDICTION_PRIVACY_EPSILON=0.1
PREDICTION_PRIVACY_DELTA=1e-5
```

## Configuration Classes

### Base Settings
```python
class Settings(BaseSettings):
    """Core configuration settings"""
    
    # Service information
    SERVICE_NAME: str = "prediction-service"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API Configuration
    API_PREFIX: str = "/api/v1"
    
    # ML Model Configuration
    MODEL_PATH: str = "models"
    CONFIDENCE_THRESHOLD: float = 0.7
    MAX_PREDICTIONS: int = 10
    
    # Database Configuration
    TIMESCALE_URL: str = "postgresql://prediction_user:prediction_pass@localhost:5432/prediction_db"
    TIMESCALE_POOL_SIZE: int = 20
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 20
    
    # Rate Limiting
    RATE_LIMIT_WINDOW: int = 60
    MAX_REQUESTS_PER_WINDOW: int = 100
    BURST_MULTIPLIER: float = 2.0
    
    # Privacy settings
    PRIVACY_EPSILON: float = 0.1
    PRIVACY_DELTA: float = 1e-5
    
    model_config = ConfigDict(
        env_prefix="PREDICTION_",
        case_sensitive=True
    )
```

## Docker Compose Configuration

### Service Configuration
```yaml
version: '3.8'

services:
  prediction_service:
    build: .
    depends_on:
      - timescaledb
      - redis
    environment:
      - PREDICTION_TIMESCALE_URL=postgresql://prediction_user:prediction_pass@timescaledb:5432/prediction_db
      - PREDICTION_REDIS_URL=redis://redis:6379/0
      - PREDICTION_MODEL_PATH=/app/models
      - PREDICTION_DEBUG=true
    ports:
      - "8002:8000"
    volumes:
      - ./models:/app/models
    networks:
      - prediction_network
    restart: on-failure
```

### Database Configuration
```yaml
timescaledb:
  image: timescale/timescaledb:latest-pg14
  environment:
    - POSTGRES_USER=prediction_user
    - POSTGRES_PASSWORD=prediction_pass
    - POSTGRES_DB=prediction_db
    - TIMESCALEDB_TELEMETRY=off
  ports:
    - "5432:5432"
  volumes:
    - timescale_data:/var/lib/postgresql/data
    - ./scripts/db_setup.sql:/docker-entrypoint-initdb.d/db_setup.sql
  networks:
    - prediction_network
  command: ["postgres", "-c", "listen_addresses=*"]
```

### Cache Configuration
```yaml
redis:
  image: redis:latest
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  networks:
    - prediction_network
```

## Performance Tuning

### Database Connection Pool
The service uses connection pooling for both TimescaleDB and Redis:

```python
# TimescaleDB Pool Configuration
async def initialize(self) -> None:
    self.pool = await asyncpg.create_pool(
        dsn=self.settings.TIMESCALE_URL,
        min_size=5,
        max_size=self.settings.TIMESCALE_POOL_SIZE
    )

# Redis Pool Configuration
self.redis_pool = redis.ConnectionPool.from_url(
    self.settings.REDIS_URL,
    max_connections=self.settings.REDIS_POOL_SIZE,
    decode_responses=True
)
```

### Rate Limiting Configuration
Configure rate limiting behavior:

```python
class RateLimitConfig:
    def __init__(
        self,
        window: int = 60,
        max_requests: int = 100,
        burst_size: Optional[int] = None
    ):
        self.window = window
        self.max_requests = max_requests
        self.burst_size = burst_size or max_requests * 2
```

## ML Model Configuration

### Model Settings
```python
class PredictionModel:
    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.7,
        use_scaler: bool = True
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.use_scaler = use_scaler
```

## Monitoring Configuration

### Prometheus Metrics
The service automatically exposes metrics at `/metrics`:
- Request counts
- Response times
- Error rates
- Custom prediction metrics

## Security Configuration

### API Key Authentication
```python
# API Key verification
async def verify_api_key(
    api_key: str = Depends(api_key_header),
    settings: Settings = Depends(get_settings)
) -> str:
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )
    return api_key
```

## Production Configuration Best Practices

1. **Environment Variables**
   - Use secrets management for sensitive values
   - Set appropriate rate limits
   - Configure pool sizes based on load

2. **Database Settings**
   - Adjust pool sizes based on connection patterns
   - Set appropriate timeouts
   - Configure SSL for production

3. **Caching Configuration**
   - Set appropriate memory limits
   - Configure eviction policies
   - Enable persistence if needed

4. **Security Settings**
   - Use strong API keys
   - Enable all security headers
   - Configure CORS appropriately

## Configuration Validation

The service validates configuration on startup:

```python
async def validate_service_health(request: Request) -> None:
    """Validate service health before processing requests"""
    connections = request.app.state.connections
    
    if not connections._initialized:
        raise HTTPException(
            status_code=503,
            detail="Service initializing or unavailable"
        )
    
    # Check database connection
    try:
        await connections.timescale_handler.pool.fetchval('SELECT 1')
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {str(e)}"
        )
```

## Development vs Production
Differentiate configurations between environments:

### Development
```env
PREDICTION_DEBUG=true
PREDICTION_TIMESCALE_POOL_SIZE=5
PREDICTION_REDIS_POOL_SIZE=5
PREDICTION_MAX_REQUESTS_PER_WINDOW=1000
```

### Production
```env
PREDICTION_DEBUG=false
PREDICTION_TIMESCALE_POOL_SIZE=20
PREDICTION_REDIS_POOL_SIZE=20
PREDICTION_MAX_REQUESTS_PER_WINDOW=100
```

## Configuration Files Location
- `.env` - Environment variables
- `pyproject.toml` - Project configuration
- `docker-compose.yml` - Container configuration
- `Dockerfile` - Build configuration

## Troubleshooting

1. **Database Connectivity**
   ```bash
   # Test database connection
   PGPASSWORD=$POSTGRES_PASSWORD psql -h timescaledb -U $POSTGRES_USER -d $POSTGRES_DB -c '\l'
   ```

2. **Redis Connectivity**
   ```bash
   # Test Redis connection
   redis-cli -h redis ping
   ```

3. **Configuration Validation**
   ```bash
   # Print current configuration
   python -c "from app.config import get_settings; print(get_settings().dict())"
   ```