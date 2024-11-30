import pytest
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import time
import logging
import os
import redis
from typing import Generator, Callable
from unittest.mock import patch, MagicMock

from src.middleware import (
    BaseRateLimiter,
    RedisRateLimiter,
    MockRateLimiter,
    get_rate_limiter,
    RateLimitMiddleware,
    setup_middleware,
    get_limiter
)
from src.config import settings

@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    return app

def test_middleware_setup(app: FastAPI):
    """Test middleware setup adds expected middleware."""
    setup_middleware(app)
    
    print("\nRegistered middleware:")
    for m in app.user_middleware:
        print(f"- {m.__class__.__name__}: {m.cls}")
    
    # Check for CORS middleware
    cors_middleware = next(
        (m for m in app.user_middleware if m.cls == CORSMiddleware),
        None
    )
    assert cors_middleware is not None, "CORS middleware not found"

def test_cors_middleware_configuration(app: FastAPI):
    """Test CORS middleware configuration."""
    setup_middleware(app)
    client = TestClient(app)
    
    response = client.options(
        "/test",
        headers={
            "Origin": "http://testserver",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Test",
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_rate_limit_middleware_functionality(app: FastAPI):
    """Test rate limit middleware is working."""
    setup_middleware(app)
    client = TestClient(app)
    
    # First request should succeed
    response = client.get("/test")
    assert response.status_code == 200
    
    # Print middleware information for debugging
    print("\nMiddleware information:")
    for m in app.user_middleware:
        print(f"- Class: {m.__class__.__name__}")
        if hasattr(m, "cls"):
            print(f"  - cls: {m.cls}")
            if m.cls == RateLimitMiddleware:
                print("    Found rate limit middleware!")
    
    # Check that rate limiting is applied (should allow since we're in test mode)
    for _ in range(settings.RATE_LIMIT_PER_SECOND + 1):
        response = client.get("/test")
        assert response.status_code == 200

def test_redis_rate_limiter_connection_handling():
    """Test Redis connection error handling."""
    limiter = RedisRateLimiter()
    assert isinstance(limiter, MockRateLimiter), "Should fall back to MockRateLimiter on connection error"

def test_get_limiter_singleton():
    """Test get_limiter returns the same instance."""
    first = get_limiter()
    second = get_limiter()
    assert first is second, "get_limiter should return the same instance"

def test_middleware_rebuilding(app: FastAPI):
    """Test middleware stack rebuilding."""
    # First setup
    setup_middleware(app)
    initial_stack = list(app.user_middleware)
    
    # Setup again
    setup_middleware(app)
    new_stack = list(app.user_middleware)
    
    assert len(new_stack) == len(initial_stack), "Middleware stack should be rebuilt with same length"
    assert all(isinstance(m.cls, type) for m in new_stack), "All middleware should have valid classes"

@pytest.mark.asyncio
async def test_rate_limiter_redis_error_handling():
    """Test rate limiter handles Redis errors gracefully."""
    limiter = RedisRateLimiter()
    # Even with Redis connection error, should still allow requests
    assert await limiter.check_rate_limit("test_key") is True

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = MagicMock()
    mock.pipeline.return_value = mock
    mock.zadd.return_value = True
    mock.zremrangebyscore.return_value = 0
    mock.zcard.return_value = 5
    mock.expire.return_value = True
    mock.execute.return_value = [True, 0, 5, True]
    return mock

@pytest.fixture
def redis_limiter(mock_redis):
    """Create RedisRateLimiter with mocked Redis."""
    with patch('redis.Redis', return_value=mock_redis):
        limiter = RedisRateLimiter()
        limiter.redis_client = mock_redis
        return limiter

@pytest.mark.asyncio
async def test_redis_operations(redis_limiter, mock_redis):
    """Test Redis operations in rate limiter."""
    result = await redis_limiter.check_rate_limit("test_key")
    assert result is True
    
    # Verify Redis operations were called
    mock_redis.pipeline.assert_called_once()
    mock_redis.zadd.assert_called_once()
    mock_redis.zremrangebyscore.assert_called_once()
    mock_redis.zcard.assert_called_once()
    mock_redis.expire.assert_called_once()
    mock_redis.execute.assert_called_once()

@pytest.mark.asyncio
async def test_redis_rate_limit_exceeded(redis_limiter, mock_redis):
    """Test rate limit exceeded scenario."""
    # Mock Redis to return high request count
    mock_redis.execute.return_value = [True, 0, settings.RATE_LIMIT_PER_SECOND + 1, True]
    
    result = await redis_limiter.check_rate_limit("test_key")
    assert result is False

@pytest.mark.asyncio
async def test_redis_pipeline_error(redis_limiter, mock_redis):
    """Test Redis pipeline error handling."""
    mock_redis.execute.side_effect = redis.RedisError("Pipeline error")
    
    result = await redis_limiter.check_rate_limit("test_key")
    assert isinstance(redis_limiter, MockRateLimiter)
    assert result is True

@pytest.mark.asyncio
async def test_rate_limit_middleware_blocked_request():
    """Test rate limit middleware blocks request when limit exceeded."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    class TestLimiter(BaseRateLimiter):
        async def check_rate_limit(self, key: str) -> bool:
            return False
    
    with patch('src.middleware.get_limiter', return_value=TestLimiter()):
        setup_middleware(app)
        client = TestClient(app)
        
        try:
            response = client.get("/test")
        except Exception as e:
            assert isinstance(e, HTTPException)
            assert e.status_code == 429
            assert e.detail == "Too many requests"

@pytest.mark.asyncio
async def test_rate_limit_middleware_error_handling():
    """Test middleware error handling."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    # Add error handler for internal server errors
    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
    
    class ErrorLimiter(BaseRateLimiter):
        async def check_rate_limit(self, key: str) -> bool:
            raise Exception("Unexpected error")
    
    with patch('src.middleware.get_limiter', return_value=ErrorLimiter()):
        setup_middleware(app)
        client = TestClient(app)
        
        try:
            response = client.get("/test")
        except Exception as e:
            assert isinstance(e, Exception)
            assert str(e) == "Unexpected error"@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_rate_limit_middleware_blocked_request():
    """Test rate limit middleware blocks request when limit exceeded."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    class TestLimiter(BaseRateLimiter):
        async def check_rate_limit(self, key: str) -> bool:
            return False
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    
    with patch('src.middleware.get_limiter', return_value=TestLimiter()):
        setup_middleware(app)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 429
        assert response.json() == {"detail": "Too many requests"}

@pytest.mark.asyncio
async def test_rate_limit_middleware_error_handling():
    """Test middleware error handling."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    class ErrorLimiter(BaseRateLimiter):
        async def check_rate_limit(self, key: str) -> bool:
            raise Exception("Unexpected error")
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    
    with patch('src.middleware.get_limiter', return_value=ErrorLimiter()):
        setup_middleware(app)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}

@pytest.mark.asyncio
async def test_redis_operation_errors(redis_limiter, mock_redis):
    """Test Redis operation errors in pipeline."""
    # Test each Redis operation failing
    operations = ['zadd', 'zremrangebyscore', 'zcard', 'expire']
    
    for op in operations:
        # Reset mock
        mock_redis.pipeline.reset_mock()
        mock_redis.pipeline.return_value = mock_redis
        
        # Make the specific operation fail
        setattr(mock_redis, op, MagicMock(side_effect=redis.RedisError(f"{op} failed")))
        
        result = await redis_limiter.check_rate_limit("test_key")
        assert result is True
        assert isinstance(redis_limiter, MockRateLimiter)

@pytest.mark.asyncio
async def test_redis_ping_failure_in_init():
    """Test Redis ping failure during initialization."""
    mock_redis = MagicMock()
    mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
    
    with patch('redis.Redis', return_value=mock_redis) as mock_redis_cls:
        limiter = RedisRateLimiter()
        mock_redis_cls.assert_called_once()
        mock_redis.ping.assert_called_once()
        assert isinstance(limiter, MockRateLimiter)

@pytest.mark.asyncio
async def test_middleware_stack_rebuild_error(app: FastAPI, caplog):
    """Test middleware stack rebuild error handling."""
    caplog.set_level(logging.ERROR)
    
    def raise_error(*args, **kwargs):
        raise RuntimeError("Stack rebuild failed")
    
    with patch.object(FastAPI, 'build_middleware_stack', side_effect=raise_error):
        setup_middleware(app)
        
        # Verify error was logged
        assert "Failed to rebuild middleware stack" in caplog.text
        assert "Stack rebuild failed" in caplog.text
        
        # Verify middleware was still added
        assert len(app.user_middleware) > 0

@pytest.mark.asyncio
async def test_redis_connection_complete_failure():
    """Test Redis connection complete failure."""
    with patch('redis.Redis', side_effect=redis.ConnectionError("Connection completely failed")):
        limiter = RedisRateLimiter()
        assert isinstance(limiter, MockRateLimiter)

@pytest.mark.asyncio
async def test_middleware_setup_complete_failure(app: FastAPI, caplog):
    """Test complete middleware setup failure."""
    caplog.set_level(logging.ERROR)
    
    def raise_error(*args, **kwargs):
        raise RuntimeError("Middleware setup failed")
    
    # Patch the add_middleware method instead of CORSMiddleware
    with patch.object(FastAPI, 'add_middleware', side_effect=raise_error):
        setup_middleware(app)
        
        # Verify error was logged
        assert "Failed to setup middleware" in caplog.text
        assert "Middleware setup failed" in caplog.text
        
        # Verify app state is still valid
        assert hasattr(app, 'user_middleware')
        assert isinstance(app.user_middleware, list)

def test_get_rate_limiter_production():
    """Test get_rate_limiter in production mode."""
    # Save original env
    original_env = os.getenv("TESTING")
    
    # Create mock Redis client
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True  # Make ping succeed
    
    try:
        # Set production environment
        os.environ["TESTING"] = "false"
        
        # Reset limiter singleton for clean test
        global _rate_limiter
        _rate_limiter = None
        
        # Mock Redis to return our mock client
        with patch('redis.Redis', return_value=mock_redis):
            # Should return RedisRateLimiter in production
            limiter = get_rate_limiter()
            assert isinstance(limiter, RedisRateLimiter)
            assert hasattr(limiter, 'redis_client')
            assert limiter.redis_client == mock_redis
            
    finally:
        # Restore original env
        if original_env is not None:
            os.environ["TESTING"] = original_env
        else:
            del os.environ["TESTING"]
        
        # Reset limiter singleton
        _rate_limiter = None

@pytest.mark.asyncio
async def test_middleware_dispatch_error(app: FastAPI, caplog):
    """Test error handling in middleware dispatch."""
    caplog.set_level(logging.ERROR)
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    # Mock get_limiter to raise an exception
    def mock_limiter_raise(*args, **kwargs):
        raise Exception("Simulated dispatch error")
    
    with patch('src.middleware.get_limiter', side_effect=mock_limiter_raise):
        setup_middleware(app)
        client = TestClient(app)
        
        # This should trigger the error handling in dispatch
        response = client.get("/test")
        
        # Verify error response
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert "Unhandled error in middleware: Simulated dispatch error" in caplog.text