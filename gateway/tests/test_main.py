import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
import logging
from httpx import AsyncClient

from src.main import (
    app, 
    lifespan, 
    general_exception_handler, 
    http_exception_handler
)

logger = logging.getLogger(__name__)

@pytest.fixture
async def async_client():
    """Async client fixture that properly handles lifespan."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

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
    async def protected_endpoint():
        raise HTTPException(
            status_code=403,
            detail="Custom error message"
        )
    
    # Add test endpoint that raises HTTPException
    app.get("/test-http-error")(protected_endpoint)
    client = TestClient(app)
    
    response = client.get("/test-http-error")
    assert response.status_code == 403
    assert response.json() == {"error": "Custom error message"}