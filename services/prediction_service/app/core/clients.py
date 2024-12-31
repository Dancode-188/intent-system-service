from typing import Dict, Any, Optional
import httpx
import logging
import asyncio
from ..config import Settings
from ..core.exceptions import ServiceError

logger = logging.getLogger(__name__)

class ServiceClient:
    """Base client for external service communication"""
    
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retries"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        retries = 3
        
        for attempt in range(retries):
            try:
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return await response.json()  # Add await here
            except httpx.HTTPError as e:
                if attempt == retries - 1:
                    raise ServiceError(f"Service request failed: {str(e)}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def close(self):
        await self._client.aclose()

class ContextServiceClient(ServiceClient):
    """Client for Context Service"""
    
    async def get_context(self, context_id: str) -> Dict[str, Any]:
        """Get context information"""
        try:
            return await self._request(
                'GET',
                f'/api/v1/context/{context_id}'
            )
        except Exception as e:
            logger.error(f"Failed to get context {context_id}: {e}")
            raise ServiceError(f"Context service error: {str(e)}")

    async def analyze_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit context for analysis"""
        try:
            return await self._request(
                'POST',
                '/api/v1/context',
                json=data
            )
        except Exception as e:
            logger.error(f"Failed to analyze context: {e}")
            raise ServiceError(f"Context analysis failed: {str(e)}")

class IntentServiceClient(ServiceClient):
    """Client for Intent Service"""
    
    async def get_patterns(self, user_id: str) -> Dict[str, Any]:
        """Get user intent patterns"""
        try:
            return await self._request(
                'GET',
                f'/api/v1/patterns/{user_id}'
            )
        except Exception as e:
            logger.error(f"Failed to get patterns for user {user_id}: {e}")
            raise ServiceError(f"Intent service error: {str(e)}")

    async def analyze_intent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit intent for analysis"""
        try:
            return await self._request(
                'POST',
                '/api/v1/intent/analyze',
                json=data
            )
        except Exception as e:
            logger.error(f"Failed to analyze intent: {e}")
            raise ServiceError(f"Intent analysis failed: {str(e)}")

class ServiceClientManager:
    """Manages service client instances"""
    
    def __init__(self, settings: Settings):
        self.context_client = ContextServiceClient(settings.CONTEXT_SERVICE_URL)
        self.intent_client = IntentServiceClient(settings.INTENT_SERVICE_URL)
        self._initialized = True

    async def close(self):
        """Close all client connections"""
        if self._initialized:
            await self.context_client.close()
            await self.intent_client.close()
            self._initialized = False