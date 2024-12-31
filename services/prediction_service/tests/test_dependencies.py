import pytest
import redis.asyncio as redis
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, HTTPException, Request
from app.dependencies import (
    verify_api_key, 
    get_rate_limiter,
    check_rate_limit,
    get_request_id,
    get_redis_client,
    get_api_dependencies,
    validate_service_health,
    get_prediction_service
)
from app.rate_limiter import EnhancedRateLimiter
from app.core.exceptions import ServiceError

@pytest.fixture
def mock_request(test_settings):
    """Create mock request with app state"""
    request = MagicMock(spec=Request)
    app = MagicMock(spec=FastAPI)
    
    # Create state with proper settings values
    state = MagicMock()
    state.settings = test_settings
    state.settings.RATE_LIMIT_WINDOW = 60
    state.settings.MAX_REQUESTS_PER_WINDOW = 100
    state.settings.BURST_MULTIPLIER = 2
    state.connections = MagicMock()
    state.connections.redis_pool = MagicMock()
    
    # Set up request mock
    request.app = app
    request.app.state = state
    request.headers = {}
    request.url = MagicMock()
    request.url.path = "/test"
    
    return request

@pytest.mark.asyncio
class TestDependencies:
    async def test_verify_api_key_valid(self):
        """Test valid API key verification"""
        result = await verify_api_key("test_api_key")
        assert result == "test_api_key"

    async def test_verify_api_key_invalid(self):
        """Test invalid API key verification"""
        with pytest.raises(HTTPException) as exc:
            await verify_api_key("invalid_key")
        assert exc.value.status_code == 401

    async def test_verify_api_key_missing(self):
        """Test missing API key"""
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(None)
        assert exc.value.status_code == 401

    async def test_get_redis_client(self, mock_request):
        """Test Redis client retrieval"""
        redis_client = get_redis_client(mock_request)
        assert isinstance(redis_client, redis.Redis)
        assert redis_client.connection_pool == mock_request.app.state.connections.redis_pool

    async def test_get_rate_limiter(self, mock_request):
        """Test rate limiter creation"""
        rate_limiter = await get_rate_limiter(mock_request)
        assert isinstance(rate_limiter, EnhancedRateLimiter)
        assert rate_limiter.config.window == 60
        assert rate_limiter.config.max_requests == 100
        assert rate_limiter.config.burst_size == 200

    async def test_check_rate_limit_allowed(self, mock_request):
        """Test rate limit check when allowed"""
        mock_limiter = AsyncMock(spec=EnhancedRateLimiter)
        mock_limiter.check_rate_limit.return_value = {
            "allowed": True,
            "reset_time": 100,
            "current_time": 0
        }
        await check_rate_limit(mock_request, "test_api_key", mock_limiter)

    async def test_check_rate_limit_exceeded(self, mock_request):
        """Test rate limit check when exceeded"""
        mock_limiter = AsyncMock(spec=EnhancedRateLimiter)
        mock_limiter.check_rate_limit.return_value = {
            "allowed": False,
            "reset_time": 100,
            "current_time": 0
        }
        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(mock_request, "test_api_key", mock_limiter)
        assert exc.value.status_code == 429

    async def test_get_request_id_provided(self):
        """Test request ID when provided"""
        request_id = "test_id"
        result = await get_request_id(request_id)
        assert result == request_id

    async def test_get_request_id_generated(self):
        """Test request ID generation when not provided"""
        result = await get_request_id(None)
        assert result.startswith("req_")

    async def test_validate_service_health_success(self, mock_request):
        """Test service health validation when healthy"""
        mock_request.app.state.connections.timescale_handler.pool.fetchval = AsyncMock(return_value=1)
        mock_request.app.state.connections.redis_pool = AsyncMock()
        await validate_service_health(mock_request)

    async def test_validate_service_health_not_initialized(self, mock_request):
        """Test health validation when not initialized"""
        mock_request.app.state.connections._initialized = False
        with pytest.raises(HTTPException) as exc:
            await validate_service_health(mock_request)
        assert exc.value.status_code == 503

    async def test_get_api_dependencies_success(self, mock_request):
        """Test successful API dependencies retrieval"""
        result = await get_api_dependencies(
            mock_request,
            request_id="test_id",
            api_key="test_api_key",
            _=None,
            service=MagicMock()
        )
        assert result["request_id"] == "test_id"
        assert result["api_key"] == "test_api_key"
        assert result["settings"] == mock_request.app.state.settings

    @pytest.mark.asyncio
    async def test_get_prediction_service(self, mock_request):
        """Test prediction service lifecycle"""
        # Mock the database handler
        mock_db = AsyncMock()
        
        # Create mock model instance with proper async methods
        mock_model_instance = AsyncMock()
        mock_model_instance._initialized = False
        mock_model_instance.initialize = AsyncMock()
        mock_model_instance.close = AsyncMock()
        mock_model_instance._closed = False

        # Setup initialization behavior
        async def mock_initialize():
            mock_model_instance._initialized = True
            return None

        # Setup cleanup behavior
        async def mock_close():
            if not mock_model_instance._closed:
                mock_model_instance._closed = True
            return None

        mock_model_instance.initialize.side_effect = mock_initialize
        mock_model_instance.close.side_effect = mock_close
        
        # Setup model class mock
        mock_model_class = MagicMock()
        mock_model_class.return_value = mock_model_instance
        
        # Setup patches
        with patch('app.dependencies.get_timescale', return_value=mock_db), \
             patch('app.service.PredictionModel', mock_model_class):
            
            # Get service from generator
            service_gen = get_prediction_service(mock_request)
            service = None
            
            # Use service
            async for svc in service_gen:
                service = svc
                assert service._initialized
                assert service.db_handler == mock_db
                assert mock_model_instance._initialized  # Verify model was initialized
                break
            
            # Force cleanup
            await service_gen.aclose()
            
            # Verify final state
            assert mock_model_instance._closed
            assert not service._initialized
            assert service.model is None

    @pytest.mark.asyncio 
    async def test_validate_service_health_db_error(self, mock_request):
        """Test health validation with database error"""
        mock_request.app.state.connections._initialized = True
        mock_request.app.state.connections.timescale_handler.pool.fetchval = AsyncMock(
            side_effect=Exception("DB Error")
        )
        
        with pytest.raises(HTTPException) as exc:
            await validate_service_health(mock_request)
        
        assert exc.value.status_code == 503
        assert "Database connection error" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_validate_service_health_redis_error(self, mock_request):
        """Test health validation with Redis error"""
        # Mock successful DB check but failed Redis check
        mock_request.app.state.connections._initialized = True
        mock_request.app.state.connections.timescale_handler.pool.fetchval = AsyncMock(return_value=1)
        
        # Setup Redis to fail
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis Error")
        
        with patch('redis.asyncio.Redis', return_value=mock_redis):
            with pytest.raises(HTTPException) as exc:
                await validate_service_health(mock_request)
            
            assert exc.value.status_code == 503
            assert "Cache connection error" in str(exc.value.detail)