import pytest
from fastapi import FastAPI, HTTPException, Request, Depends
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime
import logging
from prometheus_client import CONTENT_TYPE_LATEST
import contextlib

from app.main import app, create_application, lifespan
from app.rate_limiter import EnhancedRateLimiter, RateLimitConfig
from app.models import PatternType
from app.core.connections import ConnectionManager
from app.dependencies import (
    verify_api_key, 
    validate_service_health, 
    get_request_id,
    get_rate_limiter,
    get_intent_service,
    check_rate_limit,
    get_api_dependencies
)

# Disable logging for tests
logging.getLogger("app.main").setLevel(logging.CRITICAL)

@pytest.fixture
def mock_connection_manager(test_settings):
    """Mock connection manager"""
    manager = AsyncMock(spec=ConnectionManager)
    manager._initialized = True
    manager.settings = test_settings
    manager.neo4j_handler = AsyncMock()
    manager.redis_pool = AsyncMock()
    manager.init = AsyncMock()
    manager.close = AsyncMock()
    return manager

@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter that returns a successful response"""
    rate_limiter = AsyncMock()
    rate_limiter.check_rate_limit.return_value = {
        "allowed": True,
        "current_requests": 1,
        "remaining_requests": 99,
        "reset_time": int(datetime.utcnow().timestamp()) + 60,
        "burst_remaining": 199
    }
    return rate_limiter

@pytest.fixture
async def test_app_with_client(mock_connection_manager, test_settings):
    """Create test app with client"""
    from app.main import app

    # Configure app state
    app.state.settings = test_settings
    app.state.connections = mock_connection_manager

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app

@pytest.fixture
def mock_intent_service():
    """Mock intent service with proper async generator"""
    service = AsyncMock()
    service.analyze_intent_pattern = AsyncMock()
    service.query_patterns = AsyncMock()
    return service

@pytest.mark.asyncio
class TestMainUncovered:
    async def test_lifespan_startup_success(self, test_settings):
        """Test successful startup in lifespan (lines 34-42)"""
        app = FastAPI()
        
        # Create mock ConnectionManager
        mock_cm = AsyncMock(spec=ConnectionManager)
        mock_cm._initialized = True
        mock_cm.init = AsyncMock()
        mock_cm.close = AsyncMock()
        
        # Create mock for ConnectionManager class itself
        with patch('app.main.ConnectionManager', return_value=mock_cm):
            # Create a test lifespan context
            @contextlib.asynccontextmanager
            async def test_lifespan(app):
                try:
                    async with lifespan(app):
                        yield
                finally:
                    pass
            
            # Test the lifespan
            async with test_lifespan(app):
                assert hasattr(app.state, 'connections')
                assert hasattr(app.state, 'settings')
                assert mock_cm.init.called

            # Verify cleanup was called
            assert mock_cm.close.called

    async def test_lifespan_cleanup(self, test_settings):
        """Test cleanup in lifespan (lines 43-50)"""
        app = FastAPI()
        
        # Create mock ConnectionManager with cleanup tracking
        mock_cm = AsyncMock(spec=ConnectionManager)
        mock_cm._initialized = True
        mock_cm.init = AsyncMock()
        mock_cm.close = AsyncMock()
        cleanup_called = False
        
        async def mock_close():
            nonlocal cleanup_called
            cleanup_called = True
        
        mock_cm.close.side_effect = mock_close
        
        # Create mock for ConnectionManager class itself
        with patch('app.main.ConnectionManager', return_value=mock_cm), \
             patch('app.main.get_settings', return_value=test_settings):
            
            @contextlib.asynccontextmanager
            async def test_lifespan(app):
                try:
                    async with lifespan(app):
                        yield
                finally:
                    pass
            
            # Run the lifespan and verify cleanup
            async with test_lifespan(app):
                assert mock_cm.init.called
                assert not cleanup_called
            
            # After context exit, cleanup should be called
            assert cleanup_called
            assert mock_cm.close.called

    async def test_health_check_success(self, test_app_with_client, mock_connection_manager):
        """Test successful health check"""
        client, app = test_app_with_client
        
        # Configure mock connection manager for success scenario
        mock_connection_manager._initialized = True
        mock_connection_manager.neo4j_handler.execute_query = AsyncMock(return_value=[{"1": 1}])
        mock_connection_manager.redis_pool.ping = AsyncMock(return_value=True)

        response = await client.get(
            "/health",
            headers={"X-API-Key": "test_api_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    async def test_health_check_failure(self, test_app_with_client, mock_connection_manager):
        """Test health check failure handling"""
        client, app = test_app_with_client
        
        # Configure mock for failure scenario
        mock_connection_manager._initialized = False
        mock_connection_manager.neo4j_handler.execute_query = AsyncMock(
            side_effect=Exception("Database error")
        )

        response = await client.get(
            "/health",
            headers={"X-API-Key": "test_api_key"}
        )

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "Service initializing or unavailable" in data["detail"]

    async def test_metrics_endpoint_error(self, test_app_with_client):
        """Test metrics endpoint error handling"""
        client, _ = test_app_with_client

        with patch('app.main.generate_latest', side_effect=Exception("Metrics error")):
            response = await client.get(
                "/metrics",
                headers={"X-API-Key": "test_api_key"}
            )

            assert response.status_code == 500
            assert "Error generating metrics" in response.json()["detail"]

    async def test_analyze_intent_error(self, test_app_with_client, mock_intent_service):
        """Test intent analysis error handling"""
        client, app = test_app_with_client

        # Mock the intent service to raise an error
        mock_intent_service.analyze_intent_pattern.side_effect = Exception("Analysis error")

        # Create mock API dependencies
        async def mock_api_dependencies(request: Request, request_id: str = Depends(get_request_id)):
            return {
                "request_id": "test_request_id",
                "api_key": "test_api_key",
                "settings": app.state.settings,
                "service": mock_intent_service
            }

        # Override the entire API dependencies function
        app.dependency_overrides[get_api_dependencies] = mock_api_dependencies

        test_request = {
            "context_id": "ctx_123",  # Added required field
            "user_id": "test_user",
            "intent_data": {
                "action": "test_action"
            }
            # timestamp is optional since it has a default_factory
        }

        response = await client.post(
            "/api/v1/intent/analyze",
            json=test_request,
            headers={"X-API-Key": "test_api_key"}
        )

        print(f"\nResponse status: {response.status_code}")
        print(f"Response body: {response.json()}")

        assert response.status_code == 500
        data = response.json()
        assert "Analysis error" in data["detail"]

    async def test_query_patterns_error(self, test_app_with_client, mock_intent_service):
        """Test pattern query error handling"""
        client, app = test_app_with_client

        # Mock the intent service to raise an error
        mock_intent_service.query_patterns.side_effect = Exception("Query error")

        # Create mock API dependencies
        async def mock_api_dependencies(request: Request, request_id: str = Depends(get_request_id)):
            return {
                "request_id": "test_request_id",
                "api_key": "test_api_key",
                "settings": app.state.settings,
                "service": mock_intent_service
            }

        # Override the entire API dependencies function
        app.dependency_overrides[get_api_dependencies] = mock_api_dependencies

        test_request = {
            "user_id": "test_user",
            "pattern_type": PatternType.BEHAVIORAL.value,  # Keep this as is
            "max_depth": 3,  # This is within the valid range (1-10)
            "min_confidence": 0.7  # This is within the valid range (0.0-1.0)
        }

        response = await client.post(
            "/api/v1/patterns/query",
            json=test_request,
            headers={"X-API-Key": "test_api_key"}
        )

        print(f"\nResponse status: {response.status_code}")
        print(f"Response body: {response.json()}")

        assert response.status_code == 500
        data = response.json()
        assert "Query error" in data["detail"]

    async def test_http_exception_handler(self, test_app_with_client):
        """Test custom exception handler"""
        client, app = test_app_with_client

        async def mock_verify_api_key():
            raise HTTPException(status_code=401, detail="Invalid API key")

        app.dependency_overrides[verify_api_key] = mock_verify_api_key

        response = await client.get(
            "/health",
            headers={"X-API-Key": "invalid_key"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid API key" in data["detail"]
        assert "request_id" in data
        assert "timestamp" in data

    async def test_analyze_intent_success(self, test_app_with_client, mock_intent_service):
        """Test successful intent analysis (covers line 133)"""
        client, app = test_app_with_client

        # Set up mock response
        mock_result = {
            "pattern_id": "pat_123",
            "pattern_type": "behavioral",
            "confidence": 0.95,
            "timestamp": datetime.utcnow().isoformat(),
            "related_patterns": []
        }
        mock_intent_service.analyze_intent_pattern.return_value = mock_result

        async def mock_api_dependencies(request: Request, request_id: str = Depends(get_request_id)):
            return {
                "request_id": "test_request_id",
                "api_key": "test_api_key",
                "settings": app.state.settings,
                "service": mock_intent_service
            }

        app.dependency_overrides[get_api_dependencies] = mock_api_dependencies

        test_request = {
            "context_id": "ctx_123",
            "user_id": "test_user",
            "intent_data": {
                "action": "test_action"
            }
        }

        response = await client.post(
            "/api/v1/intent/analyze",
            json=test_request,
            headers={"X-API-Key": "test_api_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pattern_id"] == mock_result["pattern_id"]
        assert data["confidence"] == mock_result["confidence"]

    async def test_query_patterns_success(self, test_app_with_client, mock_intent_service):
        """Test successful pattern query (covers line 152)"""
        client, app = test_app_with_client

        # Set up mock response
        mock_patterns = [
            {
                "pattern_id": "pat_123",
                "pattern_type": "behavioral",
                "confidence": 0.95,
                "timestamp": datetime.utcnow().isoformat(),
                "related_patterns": []
            },
            {
                "pattern_id": "pat_124",
                "pattern_type": "behavioral",
                "confidence": 0.90,
                "timestamp": datetime.utcnow().isoformat(),
                "related_patterns": []
            }
        ]
        mock_intent_service.query_patterns.return_value = mock_patterns

        async def mock_api_dependencies(request: Request, request_id: str = Depends(get_request_id)):
            return {
                "request_id": "test_request_id",
                "api_key": "test_api_key",
                "settings": app.state.settings,
                "service": mock_intent_service
            }

        app.dependency_overrides[get_api_dependencies] = mock_api_dependencies

        test_request = {
            "user_id": "test_user",
            "pattern_type": PatternType.BEHAVIORAL.value,
            "max_depth": 3,
            "min_confidence": 0.7
        }

        response = await client.post(
            "/api/v1/patterns/query",
            json=test_request,
            headers={"X-API-Key": "test_api_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["pattern_id"] == mock_patterns[0]["pattern_id"]
        assert data[1]["pattern_id"] == mock_patterns[1]["pattern_id"]