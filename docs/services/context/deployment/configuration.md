# Context Service Configuration Guide

## Overview

This document details the configuration options and deployment settings for the Context Service. The service uses Pydantic for configuration management, ensuring type safety and validation.

## Configuration Structure

### Base Configuration

```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Configuration settings for Context Service
    """
    # Service Information
    SERVICE_NAME: str = "context-service"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # ML Model Configuration
    MODEL_NAME: str = "distilbert-base-uncased"
    MAX_SEQUENCE_LENGTH: int = 512
    BATCH_SIZE: int = 32
    
    # API Configuration
    API_PREFIX: str = "/api/v1"
    
    # Privacy Settings
    PRIVACY_EPSILON: float = 0.1
    PRIVACY_DELTA: float = 1e-5
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8000
    
    model_config = ConfigDict(
        env_prefix="CONTEXT_",
        case_sensitive=True
    )
```

## Environment Variables

### Core Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| CONTEXT_SERVICE_NAME | Service identifier | "context-service" | No |
| CONTEXT_VERSION | Service version | "0.1.0" | No |
| CONTEXT_DEBUG | Debug mode flag | False | No |

### ML Model Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| CONTEXT_MODEL_NAME | BERT model variant | "distilbert-base-uncased" | No |
| CONTEXT_MAX_SEQUENCE_LENGTH | Max input length | 512 | No |
| CONTEXT_BATCH_SIZE | Processing batch size | 32 | No |

### Privacy Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| CONTEXT_PRIVACY_EPSILON | Privacy parameter | 0.1 | No |
| CONTEXT_PRIVACY_DELTA | Privacy parameter | 1e-5 | No |

## Configuration Management

### 1. Loading Configuration

```python
from functools import lru_cache

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    """
    return Settings()

# Usage in FastAPI
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    app.state.settings = settings
```

### 2. Validation

```python
def validate_settings(settings: Settings) -> None:
    """
    Validate settings and their relationships
    """
    # Validate sequence length
    if settings.MAX_SEQUENCE_LENGTH > 512:
        raise ValueError(
            "MAX_SEQUENCE_LENGTH cannot exceed model maximum (512)"
        )
    
    # Validate batch size
    if settings.BATCH_SIZE < 1:
        raise ValueError("BATCH_SIZE must be positive")
    
    # Validate privacy parameters
    if settings.PRIVACY_EPSILON <= 0:
        raise ValueError("PRIVACY_EPSILON must be positive")
    if settings.PRIVACY_DELTA <= 0:
        raise ValueError("PRIVACY_DELTA must be positive")
```

## Environment Files

### Development (.env.development)

```ini
CONTEXT_DEBUG=true
CONTEXT_MODEL_NAME=distilbert-base-uncased
CONTEXT_MAX_SEQUENCE_LENGTH=512
CONTEXT_BATCH_SIZE=32
CONTEXT_PRIVACY_EPSILON=0.1
CONTEXT_PRIVACY_DELTA=1e-5
CONTEXT_ENABLE_METRICS=true
CONTEXT_METRICS_PORT=8000
```

### Production (.env.production)

```ini
CONTEXT_DEBUG=false
CONTEXT_MODEL_NAME=distilbert-base-uncased
CONTEXT_MAX_SEQUENCE_LENGTH=512
CONTEXT_BATCH_SIZE=64
CONTEXT_PRIVACY_EPSILON=0.05
CONTEXT_PRIVACY_DELTA=1e-6
CONTEXT_ENABLE_METRICS=true
CONTEXT_METRICS_PORT=8000
```

## Deployment Configuration

### 1. Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CONTEXT_DEBUG=false

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  context-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CONTEXT_DEBUG=false
      - CONTEXT_MODEL_NAME=distilbert-base-uncased
      - CONTEXT_MAX_SEQUENCE_LENGTH=512
      - CONTEXT_BATCH_SIZE=32
    volumes:
      - ./app:/app
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Resource Requirements

### Minimum Requirements

```yaml
resources:
  cpu: "2 cores"
  memory: "4GB"
  storage: "1GB"
```

### Recommended Requirements

```yaml
resources:
  cpu: "4 cores"
  memory: "8GB"
  storage: "2GB"
```

## Monitoring Configuration

### 1. Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'context-service'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

### 2. Logging Configuration

```python
# logging_config.py
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

## Security Configuration

### 1. CORS Configuration

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Authentication Configuration

```python
# dependencies.py
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(
    api_key: str = Depends(api_key_header),
    settings: Settings = Depends(get_settings)
) -> str:
    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="API key is required"
        )
    # Add key validation logic
    return api_key
```

## Best Practices

1. **Environment Management**
   - Use different .env files for different environments
   - Never commit sensitive values
   - Use secrets management in production

2. **Resource Management**
   - Monitor resource usage
   - Adjust batch size based on load
   - Scale horizontally when needed

3. **Security**
   - Rotate API keys regularly
   - Use HTTPS in production
   - Implement rate limiting

4. **Monitoring**
   - Enable metrics collection
   - Set up alerting
   - Monitor model performance

## Troubleshooting

### Common Issues

1. **Memory Issues**
   - Reduce batch size
   - Monitor memory usage
   - Check for memory leaks

2. **Performance Issues**
   - Adjust worker count
   - Optimize batch processing
   - Check resource utilization

3. **Configuration Issues**
   - Validate environment variables
   - Check file permissions
   - Verify configuration loading

## Deployment Checklist

- [ ] Environment variables set
- [ ] Security settings configured
- [ ] Monitoring enabled
- [ ] Resource limits set
- [ ] Health checks configured
- [ ] Logging configured
- [ ] Backups configured
- [ ] SSL/TLS configured
- [ ] API keys configured
- [ ] Rate limiting enabled