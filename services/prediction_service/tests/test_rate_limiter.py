import pytest
import redis.asyncio as redis
from unittest.mock import AsyncMock, MagicMock
from app.rate_limiter import RateLimitConfig, EnhancedRateLimiter

@pytest.fixture
def rate_limit_config():
    """Create test rate limit config"""
    return RateLimitConfig(
        window=60,
        max_requests=60,
        burst_size=120
    )

@pytest.fixture
def mock_redis():
    """Create mock redis client"""
    redis = AsyncMock()
    redis.pipeline = MagicMock()
    redis.pipeline.return_value.__aenter__.return_value = redis
    redis.pipeline.return_value.__aexit__ = AsyncMock()
    return redis

@pytest.mark.asyncio
class TestRateLimiter:
    async def test_check_rate_limit_allowed(self, rate_limit_config, mock_redis):
        """Test rate limit check when allowed"""
        mock_redis.zcard.return_value = 50
        mock_redis.execute.return_value = [0, 50, 1, True]
        
        limiter = EnhancedRateLimiter(mock_redis, rate_limit_config)
        result = await limiter.check_rate_limit("test_key", "test_endpoint")
        
        assert result["allowed"] is True
        assert result["current_requests"] == 50
        assert result["remaining_requests"] == 10
        assert "reset_time" in result
        assert "current_time" in result

    async def test_check_rate_limit_exceeded(self, rate_limit_config, mock_redis):
        """Test rate limit check when exceeded"""
        mock_redis.zcard.return_value = 121
        mock_redis.execute.return_value = [0, 121, 1, True]
        
        limiter = EnhancedRateLimiter(mock_redis, rate_limit_config)
        result = await limiter.check_rate_limit("test_key", "test_endpoint")
        
        assert result["allowed"] is False
        assert result["current_requests"] == 121
        assert result["remaining_requests"] == 0
        assert result["burst_remaining"] == 0

    async def test_check_rate_limit_first_request(self, rate_limit_config, mock_redis):
        """Test rate limit check for first request"""
        mock_redis.zcard.return_value = 0
        mock_redis.execute.return_value = [0, 0, 1, True]
        
        limiter = EnhancedRateLimiter(mock_redis, rate_limit_config)
        result = await limiter.check_rate_limit("test_key", "test_endpoint")
        
        assert result["allowed"] is True
        assert result["current_requests"] == 0
        assert result["remaining_requests"] == 60
        assert result["burst_remaining"] == 120

    async def test_check_rate_limit_burst(self, rate_limit_config, mock_redis):
        """Test rate limit burst handling"""
        mock_redis.zcard.return_value = 90
        mock_redis.execute.return_value = [0, 90, 1, True]
        
        limiter = EnhancedRateLimiter(mock_redis, rate_limit_config)
        result = await limiter.check_rate_limit("test_key", "test_endpoint")
        
        assert result["allowed"] is True
        assert result["current_requests"] == 90
        assert result["remaining_requests"] == 0
        assert result["burst_remaining"] == 30

    async def test_check_rate_limit_pipeline_error(self, rate_limit_config, mock_redis):
        """Test rate limit check with Redis error"""
        mock_redis.pipeline.return_value.__aenter__.side_effect = redis.RedisError("Test error")
        
        limiter = EnhancedRateLimiter(mock_redis, rate_limit_config)
        result = await limiter.check_rate_limit("test_key", "test_endpoint")
        
        assert result["allowed"] is True
        assert "error" in result
        assert result["error"] == "Rate limiting temporarily unavailable"

    async def test_rate_limit_config_validation(self):
        """Test rate limit config validation"""
        with pytest.raises(ValueError):
            RateLimitConfig(window=0)
            
        with pytest.raises(ValueError):
            RateLimitConfig(max_requests=0)
            
        with pytest.raises(ValueError):
            RateLimitConfig(burst_size=-1)