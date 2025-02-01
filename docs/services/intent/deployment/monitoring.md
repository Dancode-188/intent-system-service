# Intent Service Monitoring Guide

## Monitoring Overview

The Intent Service implements comprehensive monitoring across:
- Service Metrics (Prometheus)
- Visualization (Grafana)
- Logging (ELK Stack)
- Tracing (Jaeger)
- Health Checks
- Alerting

## Prometheus Metrics

### Core Metrics Setup
```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_COUNT = Counter(
    'intent_service_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'intent_service_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Pattern metrics
PATTERN_COUNT = Counter(
    'intent_service_patterns_total',
    'Total patterns analyzed',
    ['pattern_type']
)

PATTERN_CONFIDENCE = Histogram(
    'intent_service_pattern_confidence',
    'Pattern confidence distribution',
    ['pattern_type'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)

# Database metrics
DB_OPERATION_DURATION = Histogram(
    'intent_service_db_operation_duration_seconds',
    'Database operation duration',
    ['operation_type', 'database'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

DB_CONNECTION_POOL = Gauge(
    'intent_service_db_connections',
    'Number of database connections',
    ['database']
)
```

### Metric Collection Middleware
```python
class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect request metrics"""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
        finally:
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(time.time() - start_time)
        
        return response
```

## Grafana Dashboards

### Dashboard Configuration
```json
{
  "dashboard": {
    "id": null,
    "title": "Intent Service Dashboard",
    "tags": ["intent-service"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "datasource": "Prometheus",
        "targets": [{
          "expr": "rate(intent_service_requests_total[5m])",
          "legendFormat": "{{method}} {{endpoint}}"
        }]
      },
      {
        "title": "Pattern Analysis",
        "type": "graph",
        "datasource": "Prometheus",
        "targets": [{
          "expr": "rate(intent_service_patterns_total[5m])",
          "legendFormat": "{{pattern_type}}"
        }]
      }
    ]
  }
}
```

### Key Dashboards

1. **Service Overview**
   - Request rates and latencies
   - Error rates
   - Pattern analysis rates
   - Database operations

2. **Database Performance**
   - Connection pool usage
   - Query latencies
   - Cache hit rates
   - Database errors

3. **Pattern Analysis**
   - Pattern recognition rates
   - Confidence distributions
   - Processing times
   - Error rates

## Logging Configuration

### Logging Setup
```python
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "intent-service.log",
            "formatter": "json",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "loggers": {
        "app": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### Structured Logging
```python
class StructuredLogger:
    """Enhanced structured logging"""
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_event(
        self,
        event: str,
        level: str = "info",
        **kwargs
    ) -> None:
        """Log structured event with context"""
        log_data = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "intent-service",
            **kwargs
        }
        
        getattr(self.logger, level)(
            event,
            extra=log_data
        )
```

## Tracing Configuration

### Jaeger Setup
```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing():
    """Configure Jaeger tracing"""
    trace.set_tracer_provider(TracerProvider())
    
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )
    
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(
        span_processor
    )
```

### Trace Context
```python
class TraceContext:
    """Manage trace context"""
    def __init__(self, tracer: trace.Tracer):
        self.tracer = tracer
    
    async def trace_operation(
        self,
        name: str,
        **attributes
    ):
        """Create span for operation"""
        with self.tracer.start_as_current_span(
            name,
            attributes=attributes
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise
```

## Health Checks

### Health Check Implementation
```python
class HealthChecker:
    """Service health checking"""
    async def check_health(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        neo4j_health = await self._check_neo4j()
        redis_health = await self._check_redis()
        ml_health = await self._check_ml_service()
        
        return {
            "status": self._aggregate_status([
                neo4j_health["status"],
                redis_health["status"],
                ml_health["status"]
            ]),
            "components": {
                "neo4j": neo4j_health,
                "redis": redis_health,
                "ml_service": ml_health
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _check_neo4j(self) -> Dict[str, str]:
        """Check Neo4j connection"""
        try:
            await self.neo4j.execute_query("RETURN 1")
            return {"status": "healthy"}
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
```

## Alerting Configuration

### Alert Rules
```yaml
# prometheus/alerts.yml
groups:
- name: intent-service
  rules:
  - alert: HighErrorRate
    expr: |
      rate(intent_service_requests_total{
        status=~"5.*"
      }[5m]) / rate(intent_service_requests_total[5m]) > 0.01
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: High error rate detected
      
  - alert: SlowResponses
    expr: |
      histogram_quantile(0.95, 
        rate(intent_service_request_duration_seconds_bucket[5m])
      ) > 0.5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: Slow response times detected
      
  - alert: DatabaseConnectionIssues
    expr: intent_service_db_connections < 1
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: Database connection issues detected
```

### Alert Manager Configuration
```yaml
# alertmanager/config.yml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'team-email'

receivers:
- name: 'team-email'
  email_configs:
  - to: 'team@example.com'
    send_resolved: true
    
- name: 'pagerduty'
  pagerduty_configs:
  - service_key: '<pagerduty-key>'
    send_resolved: true
```

## Performance Monitoring

### Resource Usage Metrics
```python
# System metrics
SYSTEM_CPU_USAGE = Gauge(
    'intent_service_cpu_usage_percent',
    'CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'intent_service_memory_usage_bytes',
    'Memory usage in bytes'
)

def collect_system_metrics():
    """Collect system resource metrics"""
    SYSTEM_CPU_USAGE.set(psutil.cpu_percent())
    SYSTEM_MEMORY_USAGE.set(psutil.virtual_memory().used)
```

### Performance Tracking
```python
class PerformanceTracker:
    """Track service performance"""
    def __init__(self):
        self.operation_times = Histogram(
            'intent_service_operation_duration_seconds',
            'Operation duration in seconds',
            ['operation_type']
        )
    
    @contextmanager
    def track_operation(self, operation_type: str):
        """Track operation duration"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.operation_times.labels(
                operation_type=operation_type
            ).observe(duration)
```

## Monitoring Best Practices

1. **Metric Collection**
   - Use appropriate metric types
   - Follow naming conventions
   - Add relevant labels
   - Monitor cardinality

2. **Logging**
   - Use structured logging
   - Include context
   - Set appropriate levels
   - Implement log rotation

3. **Alerting**
   - Define clear thresholds
   - Avoid alert fatigue
   - Include runbooks
   - Test alert rules

4. **Dashboard Design**
   - Focus on key metrics
   - Use appropriate visualizations
   - Include legends
   - Add documentation

5. **Health Checks**
   - Check all dependencies
   - Include timeouts
   - Handle failures gracefully
   - Monitor check results