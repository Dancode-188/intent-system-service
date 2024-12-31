import pytest
from unittest.mock import patch, AsyncMock
import httpx
from app.core.clients import (
    ServiceClient,
    ContextServiceClient,
    IntentServiceClient,
    ServiceClientManager
)
from app.core.exceptions import ServiceError

class MockResponse:
    """Mock HTTP response."""
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    async def json(self):
        """Return mock json data"""
        return self._json_data

    def raise_for_status(self):
        """Raise exception for error status codes"""
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Error",
                request=None,
                response=self
            )

@pytest.mark.asyncio
async def test_context_client_get_context():
    """Test context client get_context method."""
    expected_data = {"context": "test"}
    mock_response = MockResponse(json_data=expected_data)
    client = ContextServiceClient("http://test-context")
    
    with patch("httpx.AsyncClient.request", AsyncMock(return_value=mock_response)):
        result = await client.get_context("test_context")
        assert result == expected_data

@pytest.mark.asyncio 
async def test_context_client_analyze_context():
    """Test context client analyze_context method."""
    # Test successful case
    expected_data = {"result": "success"}
    mock_response = MockResponse(json_data=expected_data)
    client = ContextServiceClient("http://test-context")
    
    with patch("httpx.AsyncClient.request", AsyncMock(return_value=mock_response)):
        result = await client.analyze_context({"test": "data"})
        assert result == expected_data

@pytest.mark.asyncio
async def test_context_client_analyze_context_error():
    """Test context client analyze_context error handling."""
    client = ContextServiceClient("http://test-context")
    
    # Test error case
    error_response = MockResponse(status_code=500)
    with patch("httpx.AsyncClient.request", AsyncMock(return_value=error_response)):
        with pytest.raises(ServiceError) as exc_info:
            await client.analyze_context({"test": "data"})
        
        assert "Context analysis failed" in str(exc_info.value)

@pytest.mark.asyncio
async def test_intent_client_get_patterns():
    """Test intent client get_patterns method."""
    expected_data = {"patterns": ["test"]}
    mock_response = MockResponse(json_data=expected_data)
    client = IntentServiceClient("http://test-intent")
    
    with patch("httpx.AsyncClient.request", AsyncMock(return_value=mock_response)):
        result = await client.get_patterns("test_user")
        assert result == expected_data

@pytest.mark.asyncio
async def test_service_error_handling():
    """Test service error handling."""
    mock_response = MockResponse(status_code=500)
    client = ServiceClient("http://test")
    
    with patch("httpx.AsyncClient.request", AsyncMock(return_value=mock_response)):
        with pytest.raises(ServiceError):
            await client._request("GET", "/test")

@pytest.mark.asyncio
async def test_client_manager_initialization(test_settings):
    """Test client manager initialization."""
    manager = ServiceClientManager(test_settings)
    
    assert manager.context_client is not None
    assert manager.intent_client is not None
    assert manager._initialized

@pytest.mark.asyncio
async def test_client_manager_cleanup(test_settings):
    """Test client manager cleanup."""
    manager = ServiceClientManager(test_settings)
    await manager.close()
    
    assert not manager._initialized

@pytest.mark.asyncio
async def test_client_error_scenarios():
    """Test client error handling"""
    client = ServiceClient("http://invalid")
    
    with pytest.raises(ServiceError):
        await client._request("GET", "/test")  # Changed from request to _request