# Intent Service Integration Guide

## Table of Contents
1. [Overview](#overview)
2. [Service Dependencies](#service-dependencies)
3. [Integration Patterns](#integration-patterns)
4. [Event System](#event-system)
5. [Error Handling](#error-handling)
6. [Client Implementation](#client-implementation)
7. [Configuration Guide](#configuration-guide)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Overview

The Intent Service interacts with several core services in the system:

- **Context Service**: Provides contextual information for intent analysis
- **Prediction Service**: Handles pattern predictions
- **Event Bus**: Manages asynchronous communication between services

### Integration Architecture
```
┌──────────────┐      ┌──────────────┐
│ Context      │◄────►│ Intent       │
│ Service      │      │ Service      │
└──────────────┘      └───────┬──────┘
                             ▲
                             │
┌──────────────┐            │
│ Prediction   │◄───────────┘
│ Service      │
└──────────────┘
```

## Service Dependencies

### Context Service Integration

```python
from typing import Dict, Any
from .client import ServiceClient

class ContextServiceClient(ServiceClient):
    """Client for Context Service integration"""
    
    async def get_context(self, context_id: str) -> Dict[str, Any]:
        return await self._request(
            'GET',
            f'/api/v1/context/{context_id}'
        )
    
    async def analyze_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request(
            'POST',
            '/api/v1/context',
            json=data
        )
```

#### Configuration Requirements
```python
# Version compatibility
REQUIRED_CONTEXT_SERVICE_VERSION = "1.0.0"
CONTEXT_API_VERSION = "v1"

# Rate limits
CONTEXT_SERVICE_RATE_LIMITS = {
    "get_context": 1000,  # requests per minute
    "analyze_context": 500  # requests per minute
}

# Timeouts
CONTEXT_SERVICE_TIMEOUTS = {
    "connect": 5.0,  # seconds
    "read": 10.0,
    "write": 10.0
}
```

### Prediction Service Integration

```python
class PredictionServiceClient(ServiceClient):
    """Client for Prediction Service integration"""
    
    async def get_predictions(
        self,
        pattern_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._request(
            'POST',
            '/api/v1/predict',
            json={
                "pattern_id": pattern_id,
                "context": context
            }
        )
```

## Integration Patterns

### Circuit Breaker Pattern

The service implements a sophisticated circuit breaker pattern to handle service failures gracefully:

```python
from core.circuit_breaker import CircuitBreaker, CircuitConfig

# Configure circuit breaker
config = CircuitConfig(
    failure_threshold=5,
    recovery_timeout=60,
    half_open_timeout=30,
    failure_window=120,
    min_throughput=5
)

# Create circuit breaker
breaker = CircuitBreaker("context-service", config)

# Use circuit breaker
async def get_context(context_id: str) -> Dict[str, Any]:
    context = CircuitContext(
        service_name="context-service",
        endpoint="/api/v1/context",
        method="GET"
    )
    
    return await breaker(
        context_client.get_context,
        context,
        context_id=context_id
    )
```

### Retry Pattern

```python
class RetryHandler:
    async def with_retry(
        self,
        operation: Callable,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential: bool = True
    ) -> Any:
        last_error = None
        delay = initial_delay
        
        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                if attempt == max_retries:
                    break
                await asyncio.sleep(delay)
                if exponential:
                    delay = min(delay * 2, max_delay)
        
        raise ServiceError(
            f"Operation failed after {max_retries} retries"
        ) from last_error
```

## Event System

### Event Types

```python
from enum import Enum

class IntentEvent(str, Enum):
    PATTERN_DETECTED = "pattern_detected"
    PATTERN_UPDATED = "pattern_updated"
    CONTEXT_CHANGED = "context_changed"
    PREDICTION_RECEIVED = "prediction_received"
```

### Event Publishing

```python
class EventPublisher:
    async def publish_pattern_event(
        self,
        pattern_id: str,
        event_type: IntentEvent,
        data: Dict[str, Any]
    ) -> None:
        event = {
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "pattern_id": pattern_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "intent_service"
        }
        await self.publish_event(event)
```

### Event Handling

```python
class EventHandler:
    async def handle_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type")
        handler = self._get_handler(event_type)
        
        if handler:
            await handler(event)
        else:
            logger.warning(f"No handler for event type: {event_type}")
```

## Error Handling

### Exception Hierarchy

```python
class CircuitBreakerError(Exception):
    """Base circuit breaker exception."""
    pass

class CircuitOpenError(CircuitBreakerError):
    """Exception raised when circuit is open."""
    def __init__(self, service_name: str, until: Optional[str] = None):
        self.service_name = service_name
        self.until = until
        message = f"Circuit breaker is open for service {service_name}"
        if until:
            message += f" until {until}"
        super().__init__(message)

class ServiceUnavailableError(CircuitBreakerError):
    """Exception raised when service is unavailable."""
    def __init__(self, service_name: str, reason: str):
        self.service_name = service_name
        self.reason = reason
        message = f"Service {service_name} is unavailable: {reason}"
        super().__init__(message)
```

### Error Handling Strategy

```python
async def handle_service_error(
    service_name: str,
    error: Exception
) -> None:
    if isinstance(error, CircuitOpenError):
        logger.warning(
            f"Circuit open for {service_name}, using fallback"
        )
        # Implement fallback strategy
        
    elif isinstance(error, ServiceUnavailableError):
        logger.error(
            f"Service {service_name} unavailable: {error.reason}"
        )
        # Implement degraded mode
        
    else:
        logger.error(
            f"Unexpected error with {service_name}: {str(error)}"
        )
        # Handle unexpected errors
```

## Client Implementation

### Base Service Client

```python
class ServiceClient:
    def __init__(
        self,
        base_url: str,
        timeout: Optional[float] = None,
        retries: int = 3
    ):
        self.base_url = base_url
        self.timeout = timeout or 30.0
        self.retries = retries
        self.retry_handler = RetryHandler()
        self.circuit_breaker = CircuitBreaker(
            f"{self.__class__.__name__}",
            CircuitConfig()
        )
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Any:
        context = CircuitContext(
            service_name=self.__class__.__name__,
            endpoint=endpoint,
            method=method
        )
        
        return await self.circuit_breaker(
            lambda: self._make_request(method, endpoint, **kwargs),
            context
        )
```

## Configuration Guide

### Environment Variables

```bash
# Service URLs
INTENT_CONTEXT_SERVICE_URL=http://context-service:8000
INTENT_PREDICTION_SERVICE_URL=http://prediction-service:8000

# Circuit Breaker Configuration
INTENT_CIRCUIT_FAILURE_THRESHOLD=5
INTENT_CIRCUIT_RECOVERY_TIMEOUT=60
INTENT_CIRCUIT_HALF_OPEN_TIMEOUT=30

# Rate Limiting
INTENT_RATE_LIMIT_WINDOW=60
INTENT_MAX_REQUESTS_PER_WINDOW=100
```

### Service Configuration

```python
class Settings(BaseSettings):
    # Service URLs
    CONTEXT_SERVICE_URL: str
    PREDICTION_SERVICE_URL: str
    
    # Circuit Breaker Settings
    CIRCUIT_FAILURE_THRESHOLD: int = 5
    CIRCUIT_RECOVERY_TIMEOUT: int = 60
    CIRCUIT_HALF_OPEN_TIMEOUT: int = 30
    
    # Rate Limiting
    RATE_LIMIT_WINDOW: int = 60
    MAX_REQUESTS_PER_WINDOW: int = 100
    
    model_config = ConfigDict(
        env_prefix="INTENT_"
    )
```

## Best Practices

### Reliability

1. **Circuit Breaking**
   - Configure appropriate thresholds
   - Implement fallback mechanisms
   - Monitor circuit state changes

2. **Retries**
   - Use exponential backoff
   - Set maximum retry limits
   - Consider operation idempotency

3. **Rate Limiting**
   - Respect service limits
   - Implement client-side throttling
   - Monitor rate limit errors

### Performance

1. **Caching**
   - Cache frequently accessed context
   - Implement cache invalidation
   - Use Redis for distributed caching

2. **Batching**
   - Batch related requests
   - Implement bulk operations
   - Configure optimal batch sizes

3. **Timeouts**
   - Set appropriate timeouts
   - Handle timeout exceptions
   - Monitor slow operations

### Monitoring

1. **Health Checks**
   ```python
   async def check_service_health(self) -> Dict[str, Any]:
       return {
           "context_service": await self.check_context_service(),
           "prediction_service": await self.check_prediction_service(),
           "circuit_breakers": self.get_circuit_states()
       }
   ```

2. **Metrics**
   ```python
   # Track service metrics
   REQUEST_COUNT = Counter(
       'service_requests_total',
       'Total service requests',
       ['service', 'endpoint']
   )
   
   REQUEST_DURATION = Histogram(
       'service_request_duration_seconds',
       'Service request duration',
       ['service', 'endpoint']
   )
   ```

3. **Logging**
   ```python
   # Structured logging
   logger.info("Service request", extra={
       "service": service_name,
       "endpoint": endpoint,
       "duration": duration,
       "status": status
   })
   ```

## Troubleshooting

### Common Issues

1. **Circuit Breaker Open**
   ```python
   # Check circuit state
   circuit_state = await breaker.get_state()
   if circuit_state == CircuitState.OPEN:
       # Implement fallback
       result = await fallback_operation()
   ```

2. **Rate Limit Exceeded**
   ```python
   # Monitor rate limits
   current_rate = await rate_limiter.get_current_rate()
   if current_rate >= threshold:
       # Implement backoff
       await asyncio.sleep(backoff_time)
   ```

3. **Service Timeout**
   ```python
   # Handle timeouts
   try:
       result = await asyncio.wait_for(
           operation(),
           timeout=TIMEOUT
       )
   except asyncio.TimeoutError:
       # Handle timeout
       logger.error("Service timeout")
   ```

### Diagnostic Tools

1. **Health Check Endpoint**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Circuit Breaker Status**
   ```bash
   curl http://localhost:8000/admin/circuits
   ```

3. **Service Metrics**
   ```bash
   curl http://localhost:8000/metrics
   ```

### Recovery Procedures

1. **Reset Circuit Breaker**
   ```python
   await circuit_breaker.reset()
   ```

2. **Clear Rate Limits**
   ```python
   await rate_limiter.reset()
   ```

3. **Reconnect Services**
   ```python
   await service_client.reconnect()
   ```