# Context Service Monitoring and Observability Guide

## Overview

This guide details the monitoring and observability setup for the Context Service, covering metrics collection, logging, tracing, and alerting configurations.

## Metrics

### 1. Service Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_COUNT = Counter(
    'context_service_requests_total',
    'Total requests processed',
    ['endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'context_service_request_duration_seconds',
    'Request duration in seconds',
    ['endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# ML metrics
EMBEDDING_GENERATION_TIME = Histogram(
    'context_service_embedding_generation_seconds',
    'Time to generate embeddings',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0]
)

MODEL_CONFIDENCE = Histogram(
    'context_service_model_confidence',
    'Model confidence distribution',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Resource metrics
MEMORY_USAGE = Gauge(
    'context_service_memory_bytes',
    'Memory usage in bytes'
)

MODEL_MEMORY = Gauge(
    'context_service_model_memory_bytes',
    'BERT model memory usage'
)
```

### 2. Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'context-service'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s
    scrape_timeout: 5s
```

### 3. Grafana Dashboards

```json
{
  "dashboard": {
    "title": "Context Service Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(context_service_requests_total[5m])",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Latency",
        "type": "heatmap",
        "targets": [
          {
            "expr": "rate(context_service_request_duration_seconds_bucket[5m])",
            "format": "heatmap"
          }
        ]
      }
    ]
  }
}
```

## Logging

### 1. Logging Configuration

```python
# logging_config.py
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'context-service.log',
            'formatter': 'json',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO'
        },
        'app.service': {
            'level': 'DEBUG',
            'propagate': True
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### 2. Structured Logging

```python
# service.py
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ContextService:
    async def process_context(self, request: ContextRequest) -> ContextResponse:
        logger.info('Processing context request', extra={
            'user_id': request.user_id,
            'action': request.action,
            'context_size': len(request.context)
        })
        try:
            # Process context...
            logger.debug('Generated embedding', extra={
                'embedding_size': len(embedding),
                'confidence': confidence
            })
        except Exception as e:
            logger.error('Context processing failed', extra={
                'error': str(e),
                'user_id': request.user_id
            })
            raise
```

## Tracing

### 1. OpenTelemetry Setup

```python
# telemetry.py
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing():
    trace.set_tracer_provider(TracerProvider(
        resource=Resource.create({
            "service.name": "context-service"
        })
    ))
    
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )
    
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
```

### 2. Request Tracing

```python
# middleware.py
from fastapi import Request
from opentelemetry import trace

async def trace_requests(request: Request, call_next):
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span(
        f"{request.method} {request.url.path}",
        kind=trace.SpanKind.SERVER,
    ) as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        
        response = await call_next(request)
        
        span.set_attribute("http.status_code", response.status_code)
        return response
```

## Alerting

### 1. Alert Rules

```yaml
# prometheus/alerts.yml
groups:
  - name: context-service
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          rate(context_service_requests_total{status="error"}[5m]) /
          rate(context_service_requests_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
          description: Error rate exceeds 10% over 5 minutes

      # High latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(context_service_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High request latency
          description: 95th percentile latency exceeds 1s

      # Memory usage
      - alert: HighMemoryUsage
        expr: context_service_memory_bytes > 1e9  # 1GB
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: High memory usage
          description: Memory usage exceeds 1GB for 15 minutes
```

### 2. Alert Manager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'team-email'

receivers:
  - name: 'team-email'
    email_configs:
      - to: 'team@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'
```

## Health Checks

### 1. Health Check Implementation

```python
# health.py
from fastapi import APIRouter
from typing import Dict

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict:
    return {
        "status": "healthy",
        "checks": {
            "model": await check_model_health(),
            "redis": await check_redis_health(),
            "memory": check_memory_health()
        }
    }

async def check_model_health() -> Dict:
    try:
        # Perform test embedding generation
        result = await service.generate_embedding("test")
        return {
            "status": "healthy",
            "details": {
                "embedding_size": len(result)
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

## Dashboard Examples

### 1. Service Overview Dashboard

```json
{
  "dashboard": {
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [{
          "expr": "rate(context_service_requests_total[5m])"
        }]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [{
          "expr": "rate(context_service_requests_total{status='error'}[5m])"
        }]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(context_service_request_duration_seconds_bucket[5m]))"
        }]
      }
    ]
  }
}
```

## Best Practices

1. **Metric Collection**
   - Use meaningful metric names
   - Add appropriate labels
   - Choose appropriate buckets for histograms
   - Monitor resource usage

2. **Logging**
   - Use structured logging
   - Include relevant context
   - Set appropriate log levels
   - Implement log rotation

3. **Alerting**
   - Define meaningful thresholds
   - Avoid alert fatigue
   - Include actionable information
   - Set up proper routing

4. **Health Checks**
   - Keep checks lightweight
   - Include dependency health
   - Set appropriate timeouts
   - Monitor check results