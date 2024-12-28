import pytest
from unittest.mock import patch
from starlette.responses import Response
from src.routing.models import RouteDefinition
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from src.discovery.registry import ServiceRegistry
from src.routing.router import RouterManager
from src.core.services.registry import register_core_services
from fastapi.responses import JSONResponse
import logging
import httpx
import jwt
from httpx import AsyncClient

from src.main import (
    app, 
    lifespan, 
    general_exception_handler, 
    http_exception_handler
)

logger = logging.getLogger(__name__)

@pytest.fixture
async def async_client(test_user):
    """Create async client with proper lifespan management."""
    test_app = FastAPI()
    
    async def mock_get_route(*args, **kwargs):
        return None

    def mock_lifespan(app):
        async def startup():
            app.state.http_client = httpx.AsyncClient()
            app.state.registry = ServiceRegistry()
            app.state.router = RouterManager(app.state.registry)
            app.state.router.get_route = mock_get_route
        async def shutdown():
            await app.state.http_client.aclose()
        return {"startup": startup, "shutdown": shutdown}

    test_app.router = app.router
    test_app.middleware = app.middleware_stack
    test_app.lifespan = mock_lifespan(test_app)

    client = AsyncClient(app=test_app, base_url="http://test")
    try:
        await client.__aenter__()
        yield client
    finally:
        await client.__aexit__(None, None, None)

@pytest.fixture
def sync_client():
    """Provide a synchronous TestClient with server exceptions disabled."""
    return TestClient(app, raise_server_exceptions=False)

@pytest.mark.asyncio
async def test_lifespan():
    """Test application lifespan management."""
    app_test = FastAPI()
    async with lifespan(app_test):
        assert hasattr(app_test.state, "http_client")
        assert isinstance(app_test.state.http_client, AsyncClient)
        
        # After context exit, client should be closed
    with pytest.raises(RuntimeError):
        await app_test.state.http_client.get("/")

def test_health_check():
    """Test health check endpoint."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "version": "1.0.0"
    }

def test_unhandled_exception(caplog):
    """Test general exception handler."""
    caplog.set_level(logging.ERROR)
    
    # Create a clean app without middleware
    test_app = FastAPI()

    # Add only the exception handlers from main app
    test_app.add_exception_handler(Exception, general_exception_handler)
    test_app.add_exception_handler(HTTPException, http_exception_handler)

    @test_app.get("/test-error")
    async def error_endpoint():
        raise ValueError("Test error")

    client = TestClient(test_app)
    response = client.get("/test-error")
    
    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error"}
    assert "Unhandled exception: Test error" in caplog.text

def test_http_exception_handler():
    """Test HTTP exception handler."""
    # Create a clean app without middleware
    test_app = FastAPI()
    
    # Add only the exception handlers
    test_app.add_exception_handler(HTTPException, http_exception_handler)
    
    @test_app.get("/test-http-error")
    async def protected_endpoint():
        raise HTTPException(
            status_code=403,
            detail="Custom error message"
        )
    
    client = TestClient(test_app)
    
    response = client.get("/test-http-error")
    assert response.status_code == 403
    assert response.json() == {"error": "Custom error message"}

def test_proxy_request_service_not_found(sync_client):
    """Test proxy request with non-existent service."""
    sync_client.app.state.registry = ServiceRegistry()
    sync_client.app.state.router = RouterManager(sync_client.app.state.registry)

    with patch.object(RouterManager, "get_route", side_effect=AsyncMock(return_value=None)):
        response = sync_client.get("/api/v1/nonexistent")
        assert response.status_code == 404

def test_proxy_request_unauthorized(sync_client):
    """Test proxy request without authentication."""
    sync_client.app.state.registry = ServiceRegistry()
    sync_client.app.state.router = RouterManager(sync_client.app.state.registry)

    route = RouteDefinition(service_name="test_service", path_prefix="/api/v1/test", auth_required=True)
    with patch.object(RouterManager, "get_route", side_effect=AsyncMock(return_value=route)):
        response = sync_client.get("/api/v1/test")
        assert response.status_code == 401

def test_proxy_request_insufficient_scope(sync_client, test_user_token):
    """Test proxy request with insufficient permissions."""
    sync_client.app.state.registry = ServiceRegistry()
    sync_client.app.state.router = RouterManager(sync_client.app.state.registry)

    headers = {"Authorization": f"Bearer {test_user_token}"}
    route = RouteDefinition(service_name="test_service", path_prefix="/api/v1/test", auth_required=True, scopes=["admin"])
    with patch.object(RouterManager, "get_route", side_effect=AsyncMock(return_value=route)):
        response = sync_client.get("/api/v1/test", headers=headers)
        assert response.status_code == 403

def test_proxy_request_success(sync_client, test_user_token):
    """Test successful proxy request."""
    sync_client.app.state.registry = ServiceRegistry()
    sync_client.app.state.router = RouterManager(sync_client.app.state.registry)

    headers = {"Authorization": f"Bearer {test_user_token}"}
    mock_response = JSONResponse(content={"status": "success"}, status_code=200)
    route = RouteDefinition(service_name="test_service", path_prefix="/api/v1/test", auth_required=True, scopes=["read"])
    mock_get_route = AsyncMock(return_value=route)
    mock_proxy = AsyncMock(return_value=mock_response)

    with patch.object(RouterManager, "get_route", side_effect=mock_get_route), \
         patch.object(RouterManager, "proxy_request", side_effect=mock_proxy):
        response = sync_client.get("/api/v1/test", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "success"}