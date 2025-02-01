# Context Service Security Guide

## Overview

This guide details the security measures and best practices implemented in the Context Service, covering authentication, authorization, data privacy, and security configurations.

## Authentication

### 1. API Key Authentication

```python
# dependencies.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=True
)

async def verify_api_key(
    api_key: str = Security(api_key_header),
    settings: Settings = Depends(get_settings)
) -> str:
    """Verify API key and return client identifier"""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )
    
    try:
        # Verify against secure key storage
        client_id = await validate_api_key(api_key)
        return client_id
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
```

### 2. API Key Management

```python
# security/key_management.py
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import secrets

class APIKeyManager:
    def __init__(self, encryption_key: bytes):
        self.fernet = Fernet(encryption_key)
    
    def generate_api_key(self, client_id: str) -> str:
        """Generate new API key"""
        # Generate random key
        key = secrets.token_urlsafe(32)
        
        # Encrypt client information
        timestamp = datetime.utcnow().isoformat()
        data = f"{client_id}:{timestamp}".encode()
        encrypted = self.fernet.encrypt(data)
        
        return f"{key}.{encrypted.decode()}"
    
    def validate_key(self, api_key: str) -> str:
        """Validate API key and return client_id"""
        try:
            key, encrypted = api_key.split(".")
            data = self.fernet.decrypt(encrypted.encode())
            client_id, timestamp = data.decode().split(":")
            
            # Check key age
            created = datetime.fromisoformat(timestamp)
            if datetime.utcnow() - created > timedelta(days=90):
                raise ValueError("Expired key")
            
            return client_id
        except Exception:
            raise ValueError("Invalid key")
```

## Rate Limiting

### 1. Rate Limiter Implementation

```python
# security/rate_limit.py
import redis.asyncio as redis
from datetime import datetime
import json

class RateLimiter:
    def __init__(
        self,
        redis_client: redis.Redis,
        window: int = 60,
        max_requests: int = 100
    ):
        self.redis = redis_client
        self.window = window
        self.max_requests = max_requests
    
    async def check_rate_limit(self, client_id: str) -> bool:
        """Check if request is within rate limits"""
        key = f"rate_limit:{client_id}"
        current_time = datetime.utcnow().timestamp()
        
        async with self.redis.pipeline() as pipe:
            try:
                # Clean old requests
                await pipe.zremrangebyscore(
                    key,
                    0,
                    current_time - self.window
                )
                
                # Count recent requests
                await pipe.zcard(key)
                
                # Add current request
                await pipe.zadd(key, {str(current_time): current_time})
                
                # Set expiry
                await pipe.expire(key, self.window)
                
                # Execute
                _, request_count, *_ = await pipe.execute()
                
                return request_count <= self.max_requests
            
            except redis.RedisError as e:
                # Log error and allow request
                logger.error(f"Rate limit check failed: {e}")
                return True
```

### 2. Rate Limit Middleware

```python
# middleware.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next
    ):
        client_id = request.state.client_id
        
        if not await rate_limiter.check_rate_limit(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )
        
        return await call_next(request)
```

## Data Privacy

### 1. Privacy-Preserving Embeddings

```python
# privacy/embeddings.py
import numpy as np
from typing import List

class PrivacyPreserver:
    def __init__(
        self,
        epsilon: float = 0.1,
        delta: float = 1e-5
    ):
        self.epsilon = epsilon
        self.delta = delta
    
    def add_noise(self, embedding: np.ndarray) -> np.ndarray:
        """Add differential privacy noise to embedding"""
        sensitivity = 1.0
        noise_scale = np.sqrt(2 * np.log(1.25/self.delta)) / self.epsilon
        
        # Generate Gaussian noise
        noise = np.random.normal(
            0,
            noise_scale * sensitivity,
            embedding.shape
        )
        
        return embedding + noise
    
    def sanitize_context(
        self,
        context: dict
    ) -> dict:
        """Remove PII from context data"""
        sensitive_keys = {'email', 'phone', 'address', 'name'}
        return {
            k: v for k, v in context.items()
            if k.lower() not in sensitive_keys
        }
```

### 2. Data Minimization

```python
# models.py
from pydantic import BaseModel, Field, validator
import re

class ContextRequest(BaseModel):
    user_id: str
    action: str
    context: dict = Field(default_factory=dict)
    
    @validator('user_id')
    def anonymize_user_id(cls, v: str) -> str:
        """Hash user ID for privacy"""
        return hashlib.sha256(v.encode()).hexdigest()
    
    @validator('context')
    def sanitize_context(cls, v: dict) -> dict:
        """Remove sensitive information from context"""
        # Remove known PII patterns
        pii_patterns = [
            r'\b[\w\.-]+@[\w\.-]+\.\w+\b',  # email
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # phone
            r'\b\d{3}-\d{2}-\d{4}\b'  # SSN
        ]
        
        sanitized = {}
        for key, value in v.items():
            if isinstance(value, str):
                for pattern in pii_patterns:
                    value = re.sub(pattern, '[REDACTED]', value)
            sanitized[key] = value
        
        return sanitized
```

## Security Headers

### 1. Security Middleware

```python
# middleware.py
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next
    ) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = \
            'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = \
            "default-src 'self'"
        
        return response
```

## Request Validation

### 1. Input Validation

```python
# validation.py
from pydantic import BaseModel, validator
from typing import Dict, Any
import re

class RequestValidator:
    @staticmethod
    def validate_content(content: str) -> bool:
        """Validate content for malicious patterns"""
        # Check for SQL injection patterns
        sql_patterns = [
            r'(\s|^)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION)',
            r'(\s|^)(OR|AND)(\s+)?\d+(\s+)?=(\s+)?\d+',
            r'--[^\n]*$'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def sanitize_input(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize input data"""
        if isinstance(data, dict):
            return {
                k: RequestValidator.sanitize_input(v)
                for k, v in data.items()
            }
        elif isinstance(data, str):
            # Remove potentially dangerous characters
            return re.sub(r'[<>&\'"]', '', data)
        elif isinstance(data, list):
            return [RequestValidator.sanitize_input(x) for x in data]
        else:
            return data
```

## Secure Configurations

### 1. Production Settings

```python
# config.py
class ProductionSettings(Settings):
    """Production-specific security settings"""
    
    # SSL/TLS Configuration
    SSL_CERT_FILE: str = "/etc/ssl/certs/service.crt"
    SSL_KEY_FILE: str = "/etc/ssl/private/service.key"
    
    # Security Settings
    ALLOWED_HOSTS: List[str] = ["api.example.com"]
    CORS_ORIGINS: List[str] = ["https://example.com"]
    
    # Rate Limiting
    RATE_LIMIT_WINDOW: int = 60
    MAX_REQUESTS_PER_WINDOW: int = 100
    
    # Privacy Settings
    PRIVACY_EPSILON: float = 0.1
    PRIVACY_DELTA: float = 1e-5
```

## Secure Deployment

### 1. Docker Security

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Run as non-root user
RUN useradd -m -s /bin/bash appuser
USER appuser

# Set secure permissions
COPY --chown=appuser:appuser . /app
WORKDIR /app

# Remove unnecessary files
RUN rm -rf tests/ docs/ *.md

# Set secure environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run with minimal privileges
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Security Monitoring

### 1. Security Logging

```python
# logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'handlers': {
        'security': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'security.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'json'
        }
    },
    'loggers': {
        'security': {
            'handlers': ['security'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

# Usage
security_logger = logging.getLogger('security')

def log_security_event(
    event_type: str,
    details: dict,
    severity: str = 'INFO'
):
    """Log security event"""
    security_logger.log(
        logging.getLevelName(severity),
        event_type,
        extra={
            'timestamp': datetime.utcnow().isoformat(),
            'details': details
        }
    )
```

## Best Practices

1. **API Security**
   - Use HTTPS only
   - Implement proper authentication
   - Validate all inputs
   - Use rate limiting

2. **Data Protection**
   - Implement data minimization
   - Use differential privacy
   - Sanitize all inputs
   - Encrypt sensitive data

3. **Deployment Security**
   - Use least privilege principle
   - Keep dependencies updated
   - Configure security headers
   - Monitor security logs

4. **Key Management**
   - Rotate keys regularly
   - Use secure storage
   - Implement key expiration
   - Monitor key usage