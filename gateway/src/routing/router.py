from typing import Dict, Optional
import logging
import httpx
from fastapi import HTTPException, Request, Response
from starlette.background import BackgroundTask

from .models import RouteDefinition, ProxyRequest
from ..discovery.registry import ServiceRegistry
from ..core.circuit_breaker.breaker import CircuitBreaker
from ..core.circuit_breaker.models import CircuitContext
from ..config import settings

logger = logging.getLogger(__name__)

class RouterManager:
    """Manages API routing and request proxying."""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.routes: Dict[str, RouteDefinition] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._http_client = httpx.AsyncClient()
        
    async def add_route(self, route: RouteDefinition) -> None:
        """Add a new route definition."""
        self.routes[route.path_prefix] = route
        
        if route.circuit_breaker:
            self.circuit_breakers[route.service_name] = CircuitBreaker(
                name=route.service_name
            )
        
        logger.info(f"Added route: {route.path_prefix} -> {route.service_name}")
        
    async def remove_route(self, path_prefix: str) -> None:
        """Remove a route definition."""
        if route := self.routes.pop(path_prefix, None):
            self.circuit_breakers.pop(route.service_name, None)
            logger.info(f"Removed route: {path_prefix}")
            
    async def get_route(self, path: str) -> Optional[RouteDefinition]:
        """Find matching route for path."""
        for prefix, route in self.routes.items():
            if path.startswith(prefix):
                return route
        return None
        
    async def proxy_request(
        self,
        request: Request,
        route: RouteDefinition
    ) -> Response:
        """Proxy request to backend service."""
        try:
            # Get service instance
            instance = await self.registry.get_instance(route.service_name)
            
            # Prepare request
            target_path = request.url.path
            if route.strip_prefix:
                target_path = target_path.replace(route.path_prefix, "", 1)
                
            target_url = f"http://{instance.host}:{instance.port}{target_path}"
            
            # Get request body if any
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                
            proxy_request = ProxyRequest(
                method=request.method,
                path=target_path,
                headers=dict(request.headers),
                query_params=dict(request.query_params),
                body=body
            )
            
            # Execute with circuit breaker if enabled
            if route.circuit_breaker:
                breaker = self.circuit_breakers[route.service_name]
                context = CircuitContext(
                    service_name=route.service_name,
                    endpoint=target_path,
                    method=request.method,
                    request_args={"url": target_url}
                )
                
                response = await breaker(
                    self._make_request,
                    context,
                    proxy_request=proxy_request
                )
            else:
                response = await self._make_request(proxy_request=proxy_request)
                
            # Create response with cleanup
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                background=BackgroundTask(response.aclose)
            )
            
        except Exception as e:
            logger.error(f"Proxy error: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail=f"Service unavailable: {str(e)}"
            )
            
    async def _make_request(self, proxy_request: ProxyRequest) -> httpx.Response:
        """Make HTTP request to backend service."""
        response = await self._http_client.request(
            method=proxy_request.method,
            url=proxy_request.path,
            headers=proxy_request.headers,
            params=proxy_request.query_params,
            content=proxy_request.body,
            timeout=30.0
        )
        return response
        
    async def close(self) -> None:
        """Cleanup resources."""
        await self._http_client.aclose()