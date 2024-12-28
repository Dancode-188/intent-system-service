from typing import Dict, Any
from ...config import settings
from ...routing.models import RouteDefinition

CORE_SERVICES: Dict[str, Dict[str, Any]] = {
    "context_service": {
        "service_name": "context_service",
        "path_prefix": f"{settings.API_V1_PREFIX}/context",
        "methods": ["GET", "POST"],
        "host": settings.CONTEXT_SERVICE_URL.split("://")[1].split(":")[0],
        "port": int(settings.CONTEXT_SERVICE_URL.split(":")[-1]),
        "check_endpoint": "/health",
        "check_interval": 30,
        "strip_prefix": True,
        "circuit_breaker": True,
        "rate_limit": True,
        "auth_required": True,
        "scopes": ["read", "write"]
    },
    "intent_service": {
        "service_name": "intent_service",
        "path_prefix": f"{settings.API_V1_PREFIX}/intent",
        "methods": ["GET", "POST"],
        "host": settings.INTENT_SERVICE_URL.split("://")[1].split(":")[0],
        "port": int(settings.INTENT_SERVICE_URL.split(":")[-1]),
        "check_endpoint": "/health",
        "check_interval": 30,
        "strip_prefix": True,
        "circuit_breaker": True,
        "rate_limit": True,
        "auth_required": True,
        "scopes": ["read", "write"]
    },
    "prediction_service": {
        "service_name": "prediction_service",
        "path_prefix": f"{settings.API_V1_PREFIX}/predict",
        "methods": ["GET", "POST"],
        "host": settings.PREDICTION_SERVICE_URL.split("://")[1].split(":")[0],
        "port": int(settings.PREDICTION_SERVICE_URL.split(":")[-1]),
        "check_endpoint": "/health",
        "check_interval": 30,
        "strip_prefix": True,
        "circuit_breaker": True,
        "rate_limit": True,
        "auth_required": True,
        "scopes": ["read"]
    },
    "realtime_service": {
        "service_name": "realtime_service",
        "path_prefix": f"{settings.API_V1_PREFIX}/realtime",
        "methods": ["GET", "POST", "WEBSOCKET"],
        "host": settings.REALTIME_SERVICE_URL.split("://")[1].split(":")[0],
        "port": int(settings.REALTIME_SERVICE_URL.split(":")[-1]),
        "check_endpoint": "/health",
        "check_interval": 15,  # More frequent for real-time
        "strip_prefix": True,
        "circuit_breaker": False,  # Websockets need different handling
        "rate_limit": True,
        "auth_required": True,
        "scopes": ["read", "write"]
    }
}

def get_route_definition(service_name: str) -> RouteDefinition:
    """Get route definition for a service."""
    if service_name not in CORE_SERVICES:
        raise KeyError(f"Unknown service: {service_name}")
    return RouteDefinition(**CORE_SERVICES[service_name])