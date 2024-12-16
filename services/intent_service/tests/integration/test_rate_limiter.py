import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import redis.asyncio as redis
from datetime import datetime
import json
from app.rate_limiter import EnhancedRateLimiter, RateLimitConfig

@pytest.mark.unit
class TestRateLimitConfig:
    def test_default_config(self):
        """Test RateLimitConfig with default values"""
        config = RateLimitConfig()
        assert config.window == 60
        assert config.max_requests == 100
        assert config.burst_size == 200

    def test_custom_config(self):
        """Test RateLimitConfig with custom values"""
        config = RateLimitConfig(
            window=30,
            max_requests=50,
            burst_size=150
        )
        assert config.window == 30
        assert config.max_requests == 50
        assert config.burst_size == 150

class MockRedisClient:
    """Mock Redis client that properly handles pipeline operations"""
    def __init__(self, pipeline_results=None):
        self.pipeline_results = pipeline_results or [0, 50, 1, True]
        self.hset = AsyncMock()
        self.expire = AsyncMock()
        self.keys = AsyncMock(return_value=[])
        self.hgetall = AsyncMock(return_value={})

    def pipeline(self, transaction=True):
        return MockRedisPipeline(self.pipeline_results)

class MockRedisPipeline:
    """Mock Redis pipeline with proper async context manager support"""
    def __init__(self, results):
        self.results = results
        self.commands = []
        self.zremrangebyscore = AsyncMock(return_value=self)
        self.zcard = AsyncMock(return_value=self)
        self.zadd = AsyncMock(return_value=self)
        self.expire = AsyncMock(return_value=self)
        self.execute = AsyncMock(return_value=self.results)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

@pytest.mark.unit
class TestEnhancedRateLimiter:
    @pytest.fixture
    def config(self):
        return RateLimitConfig(
            max_requests=100,  # Set explicit values
            burst_size=200     # to match test assumptions
        )

    @pytest.fixture
    def mock_redis(self):
        return MockRedisClient()

    @pytest.fixture
    def rate_limiter(self, mock_redis, config):
        return EnhancedRateLimiter(mock_redis, config)

    async def test_check_rate_limit_allowed(self, rate_limiter):
        """Test rate limit check when requests are allowed"""
        result = await rate_limiter.check_rate_limit("test_client", "/api/test")
        
        assert result["allowed"] is True
        assert result["current_requests"] == 50
        assert result["remaining_requests"] == 50
        assert "reset_time" in result
        assert result["burst_remaining"] == 150

    async def test_check_rate_limit_exceeded(self, config):
        """Test rate limit check when limit is exceeded"""
        # Create Redis client with a request count that exceeds burst limit
        redis_client = MockRedisClient([
            0,              # zremrangebyscore result
            250,            # zcard result (exceeds burst size of 200)
            1,              # zadd result
            True            # expire result
        ])
        rate_limiter = EnhancedRateLimiter(redis_client, config)
        
        result = await rate_limiter.check_rate_limit("test_client", "/api/test")
        
        assert result["allowed"] is False
        assert result["current_requests"] == 250
        assert result["remaining_requests"] == 0
        assert "reset_time" in result
        assert result["burst_remaining"] == 0

    async def test_check_rate_limit_redis_error(self, config):
        """Test rate limit check handling Redis errors"""
        redis_client = AsyncMock(spec=redis.Redis)
        redis_client.pipeline.side_effect = redis.RedisError("Connection error")
        rate_limiter = EnhancedRateLimiter(redis_client, config)
        
        result = await rate_limiter.check_rate_limit("test_client", "/api/test")
        
        assert result["allowed"] is True
        assert "error" in result
        assert "Rate limiting temporarily unavailable" in result["error"]

    async def test_record_usage(self, rate_limiter, mock_redis):
        """Test usage recording functionality"""
        usage_data = {"endpoint": "/api/test", "status": 200}
        client_id = "test_client"
        endpoint = "/api/test"
        
        await rate_limiter.record_usage(client_id, endpoint, usage_data)
        
        assert mock_redis.hset.await_count == 1
        assert mock_redis.expire.await_count == 1

    async def test_record_usage_redis_error(self, rate_limiter, mock_redis):
        """Test usage recording with Redis errors"""
        mock_redis.hset.side_effect = redis.RedisError("Connection error")
        
        await rate_limiter.record_usage("test_client", "/api/test", {})
        
        assert mock_redis.hset.await_count == 1

    async def test_get_usage_analytics(self, rate_limiter, mock_redis):
        """Test retrieving usage analytics"""
        mock_redis.keys.return_value = ["usage:client1:endpoint1:2024-01-01"]
        mock_redis.hgetall.return_value = {
            "2024-01-01T12:00:00": json.dumps({"count": 100})
        }
        
        analytics = await rate_limiter.get_usage_analytics("client1", "endpoint1")
        
        assert len(analytics) == 1
        assert "usage:client1:endpoint1:2024-01-01" in analytics
        
        assert mock_redis.keys.await_count == 1
        assert mock_redis.hgetall.await_count == 1

    async def test_get_usage_analytics_redis_error(self, rate_limiter, mock_redis):
        """Test analytics retrieval with Redis errors"""
        mock_redis.keys.side_effect = redis.RedisError("Connection error")
        
        analytics = await rate_limiter.get_usage_analytics("client1")
        
        assert analytics == {}
        assert mock_redis.keys.await_count == 1
        assert mock_redis.hgetall.await_count == 0

    async def test_close(self, rate_limiter):
        """Test rate limiter cleanup"""
        await rate_limiter.close()  # Should not raise any errors

    async def test_close_with_error(self, rate_limiter, mock_redis):
        """Test rate limiter cleanup with error"""
        # Create mock redis client with failing close method
        mock_redis.close = AsyncMock(side_effect=Exception("Redis cleanup error"))
        rate_limiter.redis = mock_redis  # Note: use redis not _redis since that's what's in the code

        with patch('app.rate_limiter.logger.error') as mock_logger:
            await rate_limiter.close()
            
            # Verify error was logged with correct message
            mock_logger.assert_called_once_with(
                "Error closing rate limiter: Redis cleanup error"
            )