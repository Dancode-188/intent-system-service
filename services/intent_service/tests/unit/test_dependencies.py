import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request
import uuid
from neo4j.exceptions import ServiceUnavailable
import redis.asyncio as redis

from app.dependencies import (
    verify_api_key,
    get_rate_limiter,
    check_rate_limit,
    get_request_id,
    get_intent_service,
    get_api_dependencies,
    validate_service_health
)
from app.config import Settings
from app.rate_limiter import EnhancedRateLimiter
from app.core.connections import ConnectionManager

@pytest.mark.unit
class TestDependencies:
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.app.state.settings = Settings(
            NEO4J_URI="bolt://test:7687",
            NEO4J_USER="test",
            NEO4J_PASSWORD="test",
            REDIS_URL="redis://test:6379/0",
            RATE_LIMIT_WINDOW=60,
            MAX_REQUESTS_PER_WINDOW=100,
            DEBUG=True
        )
        return request

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client"""
        client = AsyncMock(spec=redis.Redis)
        client.ping = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_neo4j_handler(self):
        """Mock Neo4j handler"""
        handler = AsyncMock()
        handler.execute_query = AsyncMock(return_value={"result": 1})
        return handler

    async def test_verify_api_key_valid(self):
        """Test verify_api_key with valid key"""
        api_key = "test_api_key"
        result = await verify_api_key(api_key)
        assert result == api_key

    async def test_verify_api_key_missing(self):
        """Test verify_api_key with missing key"""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)
        assert exc_info.value.status_code == 401
        assert "API key is required" in exc_info.value.detail

    async def test_verify_api_key_invalid(self):
        """Test verify_api_key with invalid key"""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("invalid_key")
        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    async def test_get_rate_limiter(self, mock_request, mock_redis_client):
        """Test get_rate_limiter creation"""
        with patch('app.dependencies.get_redis', return_value=mock_redis_client):
            rate_limiter = await get_rate_limiter(mock_request)
            assert isinstance(rate_limiter, EnhancedRateLimiter)
            assert rate_limiter.redis == mock_redis_client  # Changed from redis_client to redis

    async def test_check_rate_limit_allowed(self, mock_request):
        """Test check_rate_limit when allowed"""
        mock_limiter = AsyncMock(spec=EnhancedRateLimiter)
        mock_limiter.check_rate_limit.return_value = {"allowed": True, "reset_time": 100}
        
        await check_rate_limit(mock_request, "test_key", mock_limiter)
        mock_limiter.check_rate_limit.assert_called_once()

    async def test_check_rate_limit_exceeded(self, mock_request):
        """Test check_rate_limit when exceeded"""
        mock_limiter = AsyncMock(spec=EnhancedRateLimiter)
        mock_limiter.check_rate_limit.return_value = {
            "allowed": False, 
            "reset_time": 100
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(mock_request, "test_key", mock_limiter)
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail["message"]

    async def test_get_request_id_provided(self):
        """Test get_request_id with provided ID"""
        request_id = "test_id"
        result = await get_request_id(request_id)
        assert result == request_id

    async def test_get_request_id_generated(self):
        """Test get_request_id with generated ID"""
        result = await get_request_id(None)
        assert result.startswith("req_")
        assert len(result) == 12  # "req_" + 8 hex chars

    async def test_get_intent_service(self, mock_request, mock_neo4j_handler):
        """Test get_intent_service creation"""
        with patch('app.dependencies.get_neo4j', return_value=mock_neo4j_handler):
            async for service in get_intent_service(mock_request):
                # Verify the handler was set correctly via set_neo4j_handler
                assert service.neo4j == mock_neo4j_handler  # Changed from neo4j_handler to neo4j

    async def test_validate_service_health_success(self, mock_request, mock_neo4j_handler, mock_redis_client):
        """Test validate_service_health when healthy"""
        # Setup connection manager mock
        connection_manager = MagicMock()
        connection_manager._initialized = True
        connection_manager.neo4j_handler = mock_neo4j_handler
        connection_manager.redis_pool = mock_redis_client
        mock_request.app.state.connections = connection_manager

        await validate_service_health(mock_request)
        mock_neo4j_handler.execute_query.assert_called_once()
        mock_redis_client.ping.assert_called_once()

    async def test_validate_service_health_not_initialized(self, mock_request):
        """Test validate_service_health when not initialized"""
        connection_manager = MagicMock()
        connection_manager._initialized = False
        mock_request.app.state.connections = connection_manager

        with pytest.raises(HTTPException) as exc_info:
            await validate_service_health(mock_request)
        assert exc_info.value.status_code == 503
        assert "Service initializing or unavailable" in exc_info.value.detail

    async def test_validate_service_health_neo4j_error(self, mock_request, mock_neo4j_handler, mock_redis_client):
        """Test validate_service_health with Neo4j error"""
        connection_manager = MagicMock()
        connection_manager._initialized = True
        mock_neo4j_handler.execute_query.side_effect = ServiceUnavailable("Neo4j error")
        connection_manager.neo4j_handler = mock_neo4j_handler
        connection_manager.redis_pool = mock_redis_client
        mock_request.app.state.connections = connection_manager

        with pytest.raises(HTTPException) as exc_info:
            await validate_service_health(mock_request)
        assert exc_info.value.status_code == 503
        assert "Database connection error" in exc_info.value.detail

    async def test_validate_service_health_redis_error(self, mock_request, mock_neo4j_handler, mock_redis_client):
        """Test validate_service_health with Redis error"""
        connection_manager = MagicMock()
        connection_manager._initialized = True
        mock_redis_client.ping.side_effect = redis.RedisError("Redis error")
        connection_manager.neo4j_handler = mock_neo4j_handler
        connection_manager.redis_pool = mock_redis_client
        mock_request.app.state.connections = connection_manager

        with pytest.raises(HTTPException) as exc_info:
            await validate_service_health(mock_request)
        assert exc_info.value.status_code == 503
        assert "Cache connection error" in exc_info.value.detail

    async def test_get_api_dependencies(self, mock_request, mock_redis_client, mock_neo4j_handler):
        """Test get_api_dependencies with valid inputs"""
        # Mock dependencies
        request_id = "test_req_id"
        api_key = "test_api_key"
        
        # Setup rate limiter mock
        mock_rate_limiter = AsyncMock(spec=EnhancedRateLimiter)
        mock_rate_limiter.check_rate_limit.return_value = {"allowed": True, "reset_time": 100}
        
        # Mock the intent service dependency
        mock_intent_service = AsyncMock()
        async def mock_get_intent_service(_):
            yield mock_intent_service
        
        # Setup all mocks
        with patch('app.dependencies.get_rate_limiter', return_value=mock_rate_limiter), \
            patch('app.dependencies.get_neo4j', return_value=mock_neo4j_handler), \
            patch('app.dependencies.get_redis', return_value=mock_redis_client), \
            patch('app.dependencies.get_intent_service', new=mock_get_intent_service):

            # Call get_api_dependencies
            result = await get_api_dependencies(
                request=mock_request,
                request_id=request_id,
                api_key=api_key
            )

            # Verify all expected keys are present
            assert "request_id" in result
            assert "api_key" in result
            assert "settings" in result
            assert "service" in result

            # Verify values
            assert result["request_id"] == request_id
            assert result["api_key"] == api_key
            assert result["settings"] == mock_request.app.state.settings
            assert result["service"] == mock_intent_service

            # Verify rate limiter was called
            mock_rate_limiter.check_rate_limit.assert_called_once()