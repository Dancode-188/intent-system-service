# Gateway Troubleshooting Guide

## Common Issues and Solutions

### Authentication Issues

#### 1. Token Authentication Failures
```
Error: "Could not validate credentials"
```

**Possible Causes:**
- Expired token
- Invalid token signature
- Malformed token

**Solutions:**
```bash
# Check token expiration
curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=testpass"

# Verify token format
echo -n $TOKEN | base64 -d | jq
```

#### 2. Scope Authorization Failures
```
Error: "Not enough permissions"
```

**Solutions:**
- Verify required scopes in route definition
- Check user's assigned scopes
- Review token scopes:
```python
token_data = jwt.decode(token, options={"verify_signature": False})
print(f"Token scopes: {token_data.get('scopes', [])}")
```

### Circuit Breaker Issues

#### 1. Circuit Stays Open
```
Error: "Circuit breaker is open for service {service_name}"
```

**Possible Causes:**
- Service consistently failing
- Recovery timeout too long
- Health checks failing

**Solutions:**
```python
# Check circuit breaker state
print(f"Circuit state: {breaker.state}")
print(f"Last state change: {breaker.last_state_change}")
print(f"Failed requests: {breaker.stats.failed_requests}")

# Check service health
curl http://localhost:8000/health
```

#### 2. Premature Circuit Opening
```
Error: "Circuit opened after {count} failures"
```

**Solutions:**
- Adjust failure threshold
- Check failure window
- Review error conditions:
```python
print(f"Failure threshold: {breaker.config.failure_threshold}")
print(f"Failure window: {breaker.config.failure_window}")
print(f"Recent failures: {await breaker._get_recent_failures()}")
```

### Rate Limiting Issues

#### 1. Unexpected Rate Limiting
```
Error: "Too many requests"
```

**Solutions:**
- Check Redis connection:
```bash
redis-cli ping
redis-cli info
```

- Verify rate limit configuration:
```python
print(f"Rate limit: {settings.RATE_LIMIT_PER_SECOND}")
print(f"Burst limit: {settings.RATE_LIMIT_BURST}")
```

#### 2. Redis Connection Issues
```
Error: "Failed to connect to Redis"
```

**Solutions:**
```bash
# Check Redis service
docker-compose ps redis
docker-compose logs redis

# Verify Redis configuration
echo $REDIS_HOST
echo $REDIS_PORT
```

### Service Discovery Issues

#### 1. Service Not Found
```
Error: "Service '{service_name}' not found in registry"
```

**Solutions:**
- Check service registration:
```python
# List registered services
services = await registry.get_services()
for service in services:
    print(f"Service: {service.service_name}")
    print(f"Instances: {len(service.instances)}")
```

#### 2. Unhealthy Service Instances
```
Error: "No healthy instances available"
```

**Solutions:**
- Check instance health:
```python
service = await registry.get_service(service_name)
for instance_id, instance in service.instances.items():
    print(f"Instance {instance_id}:")
    print(f"  Status: {instance.status}")
    print(f"  Last check: {instance.last_check}")
```

### Request Routing Issues

#### 1. Route Not Found
```
Error: "Service not found"
```

**Solutions:**
- Verify route configuration:
```python
routes = await router.get_routes()
for prefix, route in routes.items():
    print(f"Route: {prefix}")
    print(f"  Service: {route.service_name}")
    print(f"  Methods: {route.methods}")
```

#### 2. Proxy Request Failures
```
Error: "Service unavailable"
```

**Solutions:**
- Check service status
- Verify routing configuration
- Review proxy logs:
```python
logger.debug(
    f"Proxy request: {request.method} {request.url}"
    f"\nHeaders: {request.headers}"
)
```

## Monitoring and Debugging

### 1. Enable Debug Logging
```python
# In your .env file
DEBUG=true

# In code
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
```

### 2. Monitor Circuit Breakers
```python
# Check all circuit breakers
for name, breaker in router.circuit_breakers.items():
    print(f"\nCircuit Breaker: {name}")
    print(f"State: {breaker.state}")
    print(f"Stats: {breaker.stats}")
```

### 3. Monitor Rate Limiting
```python
# Check rate limit counters
async def check_rate_limits(key: str):
    current = await redis_client.zcard(f"rate_limit:{key}")
    print(f"Current requests: {current}")
    print(f"Limit: {settings.RATE_LIMIT_PER_SECOND}")
```

### 4. Service Health Checks
```python
# Check all services health
async def check_services_health():
    for service in await registry.get_services():
        healthy = 0
        total = 0
        for instance in service.instances.values():
            total += 1
            if instance.status == ServiceStatus.HEALTHY:
                healthy += 1
        print(f"{service.service_name}: {healthy}/{total} healthy")
```

## Diagnostic Tools

### 1. Health Check Endpoint
```bash
curl http://localhost:8000/health
```

### 2. Service Registry Status
```bash
curl http://localhost:8000/api/v1/services
```

### 3. Circuit Breaker Status
```bash
curl http://localhost:8000/api/v1/circuits
```

### 4. Rate Limit Status
```bash
curl http://localhost:8000/api/v1/rate-limits
```

## Performance Optimization

### 1. Circuit Breaker Tuning
```python
# Optimize circuit breaker configuration
circuit_config = CircuitConfig(
    failure_threshold=5,      # Adjust based on service stability
    recovery_timeout=30,      # Adjust based on recovery patterns
    half_open_timeout=10,     # Adjust based on service response time
    failure_window=60,        # Adjust based on traffic patterns
    min_throughput=2         # Adjust based on traffic volume
)
```

### 2. Rate Limit Optimization
```python
# Adjust rate limits based on capacity
settings.RATE_LIMIT_PER_SECOND = 100  # Adjust based on service capacity
settings.RATE_LIMIT_BURST = 150      # Allow for traffic spikes
```

### 3. Service Discovery Optimization
```python
# Optimize health check intervals
service_config = ServiceDefinition(
    check_interval=30,        # Adjust based on service stability
    check_timeout=5,         # Adjust based on network conditions
)
```

## Recovery Procedures

### 1. Circuit Breaker Reset
```python
# Reset specific circuit breaker
await breaker.reset()
logger.info(f"Reset circuit breaker for {service_name}")
```

### 2. Service Reregistration
```python
# Reregister service
await registry.deregister_service(service_name, instance_id)
instance = await registry.register_service(registration_request)
logger.info(f"Reregistered service {service_name}")
```

### 3. Rate Limit Reset
```python
# Reset rate limit counters
await redis_client.delete(f"rate_limit:{key}")
logger.info(f"Reset rate limit for {key}")
```

## Common Error Patterns

### 1. Authentication Chain
```
Request → Token Validation → User Lookup → Scope Check
```

### 2. Service Request Chain
```
Request → Rate Limit → Circuit Breaker → Service Discovery → Proxy
```

### 3. Health Check Chain
```
Schedule → Check Endpoint → Update Status → Notify Router
```

## Need Help?

### 1. Check Logs
```bash
# Application logs
docker-compose logs gateway

# Service logs
docker-compose logs {service_name}
```

### 2. Monitor Metrics
```bash
# Prometheus metrics
curl http://localhost:9090/metrics

# Service metrics
curl http://localhost:8000/metrics
```

### 3. Debug Mode
```bash
# Enable debug mode
export DEBUG=true
uvicorn src.main:app --reload --log-level debug
```