# Gateway Security Implementation

## Overview

The API Gateway implements multiple layers of security to protect services and ensure secure communication. This document details the security implementations and best practices.

## Authentication System

### JWT Implementation
```python
from jose import jwt
from datetime import datetime, timedelta, UTC

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or 
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256"
    )
```

### Password Handling
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
```

## Authorization

### Scope-Based Access Control
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

### User Models
```python
class User(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    disabled: bool = False
    scopes: List[str] = []

class UserInDB(User):
    hashed_password: str
```

## Rate Limiting

### Redis Implementation
```python
class RedisRateLimiter:
    async def check_rate_limit(self, key: str) -> bool:
        try:
            current = int(time.time())
            pipe = self.redis_client.pipeline()

            # Add current timestamp
            pipe.zadd(key, {str(current): current})
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, current - 60)
            # Count requests
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, 60)

            # Execute pipeline
            _, _, request_count, _ = pipe.execute()
            return request_count <= settings.RATE_LIMIT_PER_SECOND
        except redis.RedisError:
            return True  # Fail open if Redis is unavailable
```

### Rate Limit Headers
```python
X-RateLimit-Limit: <limit>
X-RateLimit-Remaining: <remaining>
X-RateLimit-Reset: <reset_time>
```

## Circuit Breaker Security

### State Management
```python
class CircuitBreaker:
    async def _before_call(self) -> None:
        """Check circuit state before making call."""
        now = datetime.now(UTC)
        
        if self.state == CircuitState.OPEN:
            recovery_time = (
                self.last_state_change.timestamp() + 
                self.config.recovery_timeout
            )
            
            if now.timestamp() > recovery_time:
                # Try recovery
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self._half_open_count = 0
            else:
                raise CircuitOpenError(
                    service_name=self.name,
                    until=datetime.fromtimestamp(recovery_time)
                )
```

### Failure Tracking
```python
async def _on_failure(self, error: Exception, context: CircuitContext) -> None:
    """Handle failed call."""
    async with self._lock:
        self.stats.failed_requests += 1
        self.stats.total_requests += 1
        
        if self.state == CircuitState.CLOSED:
            failure_count = await self._get_recent_failures()
            
            if failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.now(UTC)
```

## Service Authentication

### Service Registry Security
```python
async def register_service(self, request: RegistrationRequest) -> ServiceInstance:
    """Register a new service instance with security checks."""
    async with self._lock:
        # Validate service credentials
        if not await self._validate_service_credentials(request):
            raise SecurityError("Invalid service credentials")
            
        # Create instance with secure defaults
        instance = ServiceInstance(
            instance_id=f"{request.host}:{request.port}",
            host=request.host,
            port=request.port,
            status=ServiceStatus.STARTING,
            metadata=request.metadata
        )
```

## CORS Security

### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)
```

## Request/Response Security

### Secure Headers
```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
}
```

## Security Best Practices

### 1. Authentication & Authorization
- Use strong password hashing (bcrypt)
- Implement JWT token expiration
- Validate all user input
- Implement proper scope checking
- Regular token rotation

### 2. Rate Limiting
- Implement per-user and per-IP limits
- Use sliding window algorithm
- Configure appropriate thresholds
- Monitor for abuse patterns
- Implement retry-after headers

### 3. Circuit Breaker
- Configure appropriate thresholds
- Implement secure state transitions
- Monitor breaker status
- Implement fallback mechanisms
- Log security events

### 4. Service Registry
- Validate service credentials
- Implement service authentication
- Regular health checks
- Secure service metadata
- Monitor for suspicious patterns

### 5. General Security
- Use HTTPS only
- Implement proper CORS policies
- Set secure headers
- Regular security audits
- Monitor for vulnerabilities

## Security Monitoring

### Logging
```python
logger.info("Security event", extra={
    "event_type": "security_audit",
    "user_id": user_id,
    "action": action,
    "status": status,
    "timestamp": datetime.now(UTC).isoformat()
})
```

### Metrics
- Authentication failures
- Rate limit hits
- Circuit breaker trips
- Service registration attempts
- Security policy violations

## Incident Response

### Security Event Handling
1. Detect security event
2. Log incident details
3. Apply security measures
4. Notify administrators
5. Update security policies

### Recovery Procedures
1. Isolate affected components
2. Verify system integrity
3. Apply security patches
4. Restore secure state
5. Update documentation

## Security Updates

### Regular Updates
- Monitor security advisories
- Update dependencies
- Patch vulnerabilities
- Update security policies
- Review security controls