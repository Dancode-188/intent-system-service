from prometheus_client import Counter, Histogram, Gauge
import time
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

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

# Query metrics
QUERY_DURATION = Histogram(
    'intent_service_query_duration_seconds',
    'Duration of pattern queries',
    ['operation_type'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

QUERY_ERRORS = Counter(
    'intent_service_query_errors_total',
    'Total query errors',
    ['operation_type', 'error_type']
)

def track_pattern_metrics(pattern_type: str, confidence: float) -> None:
    """
    Track pattern-related metrics
    """
    try:
        PATTERN_COUNT.labels(pattern_type=pattern_type).inc()
        PATTERN_CONFIDENCE.labels(pattern_type=pattern_type).observe(confidence)
    except Exception as e:
        logger.error(f"Error tracking pattern metrics: {e}", exc_info=True)

def track_query_metrics(operation_type: str):
    """
    Decorator to track query metrics
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                QUERY_DURATION.labels(
                    operation_type=operation_type
                ).observe(time.time() - start_time)
                return result
            except Exception as e:
                QUERY_ERRORS.labels(
                    operation_type=operation_type,
                    error_type=type(e).__name__
                ).inc()
                raise
            finally:
                # Additional timing metric if needed
                duration = time.time() - start_time
                if duration > 1.0:  # Log slow queries
                    logger.warning(
                        f"Slow query detected for {operation_type}: {duration:.2f}s"
                    )
        return wrapper
    return decorator