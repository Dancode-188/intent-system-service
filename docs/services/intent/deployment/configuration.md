# Intent Service Configuration Guide

## Configuration Overview

The Intent Service uses a hierarchical configuration system with the following precedence (highest to lowest):
1. Environment variables
2. `.env` file
3. Default values

## Environment Variables

### Core Service Settings
```bash
# Service Information
INTENT_SERVICE_NAME=intent-service
INTENT_VERSION=0.1.0
INTENT_DEBUG=false

# API Configuration
INTENT_API_PREFIX=/api/v1
```

### Database Configuration

#### Neo4j Settings
```bash
# Neo4j Connection
INTENT_NEO4J_URI=bolt://localhost:7687
INTENT_NEO4J_USER=neo4j
INTENT_NEO4J_PASSWORD=password
INTENT_NEO4J_POOL_SIZE=50
INTENT_NEO4J_MAX_AGE=3600
INTENT_NEO4J_MAX_RETRY=3
INTENT_NEO4J_RETRY_DELAY=1
```

#### Redis Settings
```bash
# Redis Connection
INTENT_REDIS_URL=redis://localhost:6379/0
INTENT_REDIS_POOL_SIZE=20
INTENT_REDIS_TIMEOUT=10
INTENT_REDIS_RETRY_ATTEMPTS=3
```

### Pattern Analysis Settings
```bash
# Graph Configuration
INTENT_MAX_PATTERN_DEPTH=5
INTENT_MIN_PATTERN_CONFIDENCE=0.6
INTENT_MAX_RELATIONSHIPS=1000
```

### Rate Limiting
```bash
# Rate Limiting
INTENT_RATE_LIMIT_WINDOW=60
INTENT_MAX_REQUESTS_PER_WINDOW=100
INTENT_BURST_MULTIPLIER=2.0
```

### Cache Configuration
```bash
# Caching
INTENT_CACHE_TTL=3600
INTENT_CACHE_ENABLED=true
```

### Monitoring
```bash
# Monitoring Settings
INTENT_ENABLE_METRICS=true
INTENT_METRICS_PORT=8001
INTENT_LOG_LEVEL=INFO
```

## Configuration Validation

### Validation Rules
```python
def validate_settings(settings: Settings) -> None:
    """Validate settings and their relationships"""
    if settings.MAX_PATTERN_DEPTH > 10:
        raise ValueError("MAX_PATTERN_DEPTH cannot exceed 10")
        
    if settings.MIN_PATTERN_CONFIDENCE < 0 or \
       settings.MIN_PATTERN_CONFIDENCE > 1:
        raise ValueError("MIN_PATTERN_CONFIDENCE must be between 0 and 1")
        
    if settings.RATE_LIMIT_WINDOW < 1:
        raise ValueError("RATE_LIMIT_WINDOW must be positive")
        
    if settings.NEO4J_POOL_SIZE < 1:
        raise ValueError("NEO4J_POOL_SIZE must be positive")
```

## Docker Environment

### Docker Compose Configuration
```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.9.0
    environment:
      - NEO4J_AUTH=neo4j/development
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  intent-service:
    build: .
    environment:
      - INTENT_NEO4J_URI=bolt://neo4j:7687
      - INTENT_REDIS_URL=redis://redis:6379/0
      - INTENT_DEBUG=false
    depends_on:
      - neo4j
      - redis
```

## Production Considerations

### Security Settings
```bash
# Production Security
INTENT_API_KEY=secure_api_key
INTENT_ENABLE_SSL=true
INTENT_SSL_CERT_PATH=/path/to/cert
INTENT_SSL_KEY_PATH=/path/to/key
```

### Performance Tuning
```bash
# Performance Settings
INTENT_WORKER_COUNT=4
INTENT_THREAD_POOL_SIZE=20
INTENT_MAX_CONNECTIONS=1000
```

### Logging Configuration
```bash
# Logging Settings
INTENT_LOG_FORMAT=json
INTENT_LOG_FILE=/var/log/intent-service.log
INTENT_LOG_ROTATION=1d
```

## Development Setup

### Local Development
```bash
# Development Settings
INTENT_DEBUG=true
INTENT_LOG_LEVEL=DEBUG
INTENT_NEO4J_URI=bolt://localhost:7687
INTENT_REDIS_URL=redis://localhost:6379/0
```

### Testing Configuration
```bash
# Test Settings
INTENT_TESTING=true
INTENT_TEST_NEO4J_URI=bolt://localhost:7688
INTENT_TEST_REDIS_URL=redis://localhost:6380/0
```

## Configuration Best Practices

### Security
1. Never commit sensitive configuration to version control
2. Use environment-specific .env files
3. Rotate API keys regularly
4. Use secure password management

### Performance
1. Adjust pool sizes based on load
2. Monitor and tune cache TTLs
3. Configure appropriate rate limits
4. Set reasonable timeout values

### Monitoring
1. Enable metrics in production
2. Configure appropriate log levels
3. Set up log aggregation
4. Enable tracing when needed

## Troubleshooting

### Common Issues

1. **Database Connection Failures**
```bash
# Check connectivity
INTENT_NEO4J_MAX_RETRY=5
INTENT_NEO4J_RETRY_DELAY=2
```

2. **Rate Limiting Issues**
```bash
# Adjust rate limiting
INTENT_RATE_LIMIT_WINDOW=120
INTENT_BURST_MULTIPLIER=3.0
```

3. **Memory Problems**
```bash
# Tune memory usage
INTENT_CACHE_TTL=1800
INTENT_MAX_CONNECTIONS=500
```

### Health Checks
```bash
# Health check configuration
INTENT_HEALTH_CHECK_INTERVAL=30
INTENT_HEALTH_CHECK_TIMEOUT=5
```