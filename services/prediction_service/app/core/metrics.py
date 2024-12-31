from prometheus_client import Counter, Histogram, Gauge
import time
import functools
import logging

logger = logging.getLogger(__name__)

# Service integration metrics
SERVICE_REQUEST_COUNT = Counter(
    'prediction_service_integration_requests_total',
    'Total number of requests to external services',
    ['service', 'endpoint', 'status']
)

SERVICE_REQUEST_DURATION = Histogram(
    'prediction_service_integration_request_duration_seconds',
    'Duration of requests to external services',
    ['service', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

SERVICE_HEALTH = Gauge(
    'prediction_service_integration_health',
    'Health status of integrated services',
    ['service']
)

# Feature enrichment metrics
ENRICHMENT_SUCCESS = Counter(
    'prediction_service_feature_enrichment_total',
    'Total number of successful feature enrichments',
    ['type']
)

ENRICHMENT_FAILURES = Counter(
    'prediction_service_feature_enrichment_failures_total',
    'Total number of feature enrichment failures',
    ['type', 'reason']
)

# Prediction analysis metrics
PREDICTION_ANALYSIS_COUNT = Counter(
    'prediction_service_analysis_total',
    'Total number of predictions analyzed',
    ['service']
)

PREDICTION_ANALYSIS_ERRORS = Counter(
    'prediction_service_analysis_errors_total',
    'Total number of prediction analysis errors',
    ['service', 'error_type']
)

def track_service_request(service: str, endpoint: str):
    """Decorator to track service request metrics"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                SERVICE_REQUEST_COUNT.labels(
                    service=service,
                    endpoint=endpoint,
                    status="success"
                ).inc()
                return result
            except Exception as e:
                SERVICE_REQUEST_COUNT.labels(
                    service=service,
                    endpoint=endpoint,
                    status="error"
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                SERVICE_REQUEST_DURATION.labels(
                    service=service,
                    endpoint=endpoint
                ).observe(duration)
        return wrapper
    return decorator

def track_enrichment(feature_type: str):
    """Decorator to track feature enrichment metrics"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                ENRICHMENT_SUCCESS.labels(type=feature_type).inc()
                return result
            except Exception as e:
                ENRICHMENT_FAILURES.labels(
                    type=feature_type,
                    reason=type(e).__name__
                ).inc()
                raise
        return wrapper
    return decorator

class MetricsManager:
    """Manages service metrics collection"""
    
    @staticmethod
    def update_service_health(service: str, is_healthy: bool):
        """Update service health status"""
        SERVICE_HEALTH.labels(service=service).set(1 if is_healthy else 0)

    @staticmethod
    def record_prediction_analysis(service: str, success: bool, error_type: str = None):
        """Record prediction analysis attempt"""
        PREDICTION_ANALYSIS_COUNT.labels(service=service).inc()
        if not success:
            PREDICTION_ANALYSIS_ERRORS.labels(
                service=service,
                error_type=error_type
            ).inc()