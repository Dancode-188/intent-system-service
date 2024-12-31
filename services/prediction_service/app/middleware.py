import logging
import time
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Metrics
REQUEST_COUNT = Counter(
    'prediction_service_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'prediction_service_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

class TimingMiddleware(BaseHTTPMiddleware):
    """Add timing information and metrics tracking to requests"""
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid4()).replace("-", "")[:16]
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = f"req_{request_id}"
            
            # Track metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Request failed: {e}")
            raise

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response