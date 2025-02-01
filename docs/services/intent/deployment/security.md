# Intent Service Security Documentation

## Security Overview

The Intent Service implements multiple layers of security:
- API Authentication & Authorization
- Rate Limiting
- Data Privacy Protection
- Secure Data Storage
- Access Control
- Monitoring & Auditing

## Authentication System

### API Key Authentication
```python
async def verify_api_key(
    api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """
    Verify the API key provided in the request header
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )
    
    if not await validate_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return api_key
```

### API Key Management

1. **Key Generation**
```python
def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"int_{secrets.token_urlsafe(32)}"
```

2. **Key Storage**
```python
async def store_api_key(key: str, metadata: dict) -> None:
    """Store API key with metadata"""
    await redis_client.hset(
        f"apikey:{key}",
        mapping={
            "created_at": datetime.utcnow().isoformat(),
            "metadata": json.dumps(metadata)
        }
    )
```

3. **Key Rotation**
```python
async def rotate_api_key(old_key: str) -> str:
    """Rotate an existing API key"""
    new_key = generate_api_key()
    metadata = await get_key_metadata(old_key)
    await store_api_key(new_key, metadata)
    await invalidate_api_key(old_key)
    return new_key
```

## Rate Limiting

### Configuration
```python
class RateLimitConfig:
    """Rate limit configuration"""
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

### Implementation
```python
class EnhancedRateLimiter:
    """Enhanced rate limiter with Redis backend"""
    async def check_rate_limit(
        self,
        client_id: str,
        endpoint: str
    ) -> Dict[str, Any]:
        key = f"rate_limit:{client_id}:{endpoint}"
        now = datetime.utcnow().timestamp()
        window_start = int(now - self.config.window)
        
        try:
            # Use Redis pipeline for atomic operations
            async with self.redis.pipeline() as pipe:
                await pipe.zremrangebyscore(key, 0, window_start)
                await pipe.zcard(key)
                await pipe.zadd(key, {str(now): now})
                await pipe.expire(key, self.config.window * 2)
                _, request_count, _, _ = await pipe.execute()
                
            return {
                "allowed": request_count <= self.config.burst_size,
                "current_requests": request_count,
                "remaining": max(0, self.config.max_requests - request_count)
            }
        except redis.RedisError as e:
            logger.error(f"Rate limiting error: {e}")
            return {"allowed": True}  # Fail open
```

## Data Privacy Protection

### Differential Privacy
```python
class DifferentialPrivacy:
    """Implements differential privacy for pattern analysis"""
    def __init__(self, epsilon: float = 0.1, delta: float = 1e-5):
        self.epsilon = epsilon
        self.delta = delta
    
    def add_noise(self, data: np.ndarray) -> np.ndarray:
        """Add Laplace noise to protect privacy"""
        sensitivity = self.calculate_sensitivity(data)
        noise = np.random.laplace(
            0,
            sensitivity / self.epsilon,
            data.shape
        )
        return data + noise
```

### Data Anonymization
```python
class DataAnonymizer:
    """Anonymizes user data"""
    def anonymize_data(self, user_data: dict) -> dict:
        return {
            "anonymous_id": self.generate_anonymous_id(),
            "vectorized_data": self.vectorize_sensitive_data(user_data),
            "aggregate_patterns": self.extract_patterns(user_data)
        }
```

## Secure Data Storage

### Neo4j Security
```python
class Neo4jHandler:
    """Secure Neo4j database handler"""
    async def connect(self) -> None:
        self.driver = AsyncGraphDatabase.driver(
            self.settings.NEO4J_URI,
            auth=(
                self.settings.NEO4J_USER,
                self.settings.NEO4J_PASSWORD
            ),
            encrypted=True,
            trust=TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
        )
```

### Redis Security
```python
class RedisHandler:
    """Secure Redis connection handler"""
    async def initialize(self) -> None:
        self.redis_pool = redis.ConnectionPool.from_url(
            self.settings.REDIS_URL,
            ssl=True,
            ssl_cert_reqs="required",
            ssl_ca_certs="/path/to/ca.pem"
        )
```

## Access Control

### Role-Based Access Control
```python
class RBACHandler:
    """Role-based access control handler"""
    def __init__(self):
        self.roles = {
            "admin": ["read", "write", "delete"],
            "analyst": ["read", "write"],
            "viewer": ["read"]
        }
    
    async def check_permission(
        self,
        user_role: str,
        required_permission: str
    ) -> bool:
        if user_role not in self.roles:
            return False
        return required_permission in self.roles[user_role]
```

### Resource Access Control
```python
class ResourceAccessControl:
    """Controls access to resources"""
    async def validate_access(
        self,
        user_id: str,
        resource_id: str,
        action: str
    ) -> bool:
        # Check ownership
        owner = await self.get_resource_owner(resource_id)
        if owner == user_id:
            return True
            
        # Check shared access
        access_list = await self.get_resource_access_list(resource_id)
        return user_id in access_list.get(action, [])
```

## Security Headers

### Middleware Configuration
```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": 
                "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'"
        })
        
        return response
```

## Audit Logging

### Audit Trail
```python
class AuditLogger:
    """Logs security-relevant events"""
    async def log_event(
        self,
        event_type: str,
        user_id: str,
        resource_id: str,
        action: str,
        status: str
    ) -> None:
        await self.db.store_audit_log({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "resource_id": resource_id,
            "action": action,
            "status": status,
            "ip_address": self.get_client_ip(),
            "user_agent": self.get_user_agent()
        })
```

## GDPR Compliance

### Data Subject Rights
```python
class GDPRHandler:
    """Handles GDPR compliance"""
    async def handle_data_request(
        self,
        user_id: str,
        request_type: str
    ) -> Dict[str, Any]:
        if request_type == "access":
            return await self.get_user_data(user_id)
        elif request_type == "delete":
            return await self.delete_user_data(user_id)
        elif request_type == "export":
            return await self.export_user_data(user_id)
```

### Data Retention
```python
class DataRetentionPolicy:
    """Implements data retention policies"""
    async def apply_retention_policy(self) -> None:
        # Remove patterns older than retention period
        cutoff = datetime.utcnow() - timedelta(
            days=self.settings.PATTERN_RETENTION_DAYS
        )
        
        await self.neo4j.execute_query(
            """
            MATCH (p:Pattern)
            WHERE p.created_at < $cutoff
            DELETE p
            """,
            {"cutoff": cutoff.isoformat()}
        )
```

## Security Best Practices

1. **API Security**
   - Use HTTPS only
   - Implement rate limiting
   - Validate all inputs
   - Use secure headers

2. **Data Security**
   - Encrypt sensitive data
   - Use differential privacy
   - Implement data anonymization
   - Regular security audits

3. **Access Control**
   - Implement RBAC
   - Validate resource access
   - Audit all access attempts
   - Regular permission reviews

4. **Infrastructure Security**
   - Use secure configurations
   - Regular updates
   - Network isolation
   - Security monitoring

5. **Incident Response**
   - Incident detection
   - Response procedures
   - Recovery plans
   - Post-incident analysis

## Security Monitoring

### Metrics Collection
```python
# Security-related metrics
SECURITY_EVENTS = Counter(
    'intent_service_security_events_total',
    'Total security events',
    ['event_type', 'status']
)

AUTH_FAILURES = Counter(
    'intent_service_auth_failures_total',
    'Total authentication failures',
    ['auth_type']
)

RATE_LIMIT_HITS = Counter(
    'intent_service_rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint']
)
```

### Alert Configuration
```yaml
# Prometheus alert rules
groups:
- name: SecurityAlerts
  rules:
  - alert: HighAuthFailures
    expr: rate(intent_service_auth_failures_total[5m]) > 10
    labels:
      severity: critical
    annotations:
      description: High rate of authentication failures
      
  - alert: RateLimitAbuse
    expr: rate(intent_service_rate_limit_hits_total[1m]) > 100
    labels:
      severity: warning
    annotations:
      description: Possible rate limit abuse detected
```