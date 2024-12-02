import pytest
from fastapi import HTTPException
from unittest.mock import Mock, patch
from app.dependencies import (
    verify_api_key,
    RateLimiter,
    get_rate_limiter,
    check_rate_limit,
    get_request_id,
    get_api_dependencies
)
from app.config import Settings

@pytest.mark.asyncio
async def test_verify_api_key():
    # Test with valid API key
    api_key = "test_api_key"
    result = await verify_api_key(api_key)
    assert result == api_key

    # Test with invalid API key
    with pytest.raises(HTTPException) as exc:
        await verify_api_key("invalid_key")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"

    # Test with missing API key
    with pytest.raises(HTTPException) as exc:
        await verify_api_key("")
    assert exc.value.status_code == 401
    assert exc.value.detail == "API key is required"

@pytest.mark.asyncio
async def test_rate_limiter(mock_redis):
    rate_limiter = RateLimiter(mock_redis)
    client_id = "test_client"
    
    # Test first request (should be allowed)
    assert await rate_limiter.check_rate_limit(client_id) is True
    mock_redis.setex.assert_called_once()

    # Test within limits
    mock_redis.get.return_value = "50"
    assert await rate_limiter.check_rate_limit(client_id) is True
    mock_redis.incr.assert_called_once()

    # Test exceeding limits
    mock_redis.get.return_value = "100"
    assert await rate_limiter.check_rate_limit(client_id) is False

@pytest.mark.asyncio
async def test_get_rate_limiter(settings):
    rate_limiter = await get_rate_limiter(settings)
    assert isinstance(rate_limiter, RateLimiter)

@pytest.mark.asyncio
async def test_check_rate_limit(mock_rate_limiter):
    request = Mock()
    
    # Test successful rate limit check
    mock_rate_limiter.check_rate_limit.return_value = True
    await check_rate_limit(request, "test_key", mock_rate_limiter)

    # Test rate limit exceeded
    mock_rate_limiter.check_rate_limit.return_value = False
    with pytest.raises(HTTPException) as exc:
        await check_rate_limit(request, "test_key", mock_rate_limiter)
    assert exc.value.status_code == 429

@pytest.mark.asyncio
async def test_get_request_id():
    # Test with provided request ID
    request_id = "test_id"
    result = await get_request_id(request_id)
    assert result == request_id

    # Test with no request ID (should generate one)
    result = await get_request_id(None)
    assert result.startswith("req_")

@pytest.mark.asyncio
async def test_get_api_dependencies(settings):
    request_id = "test_id"
    api_key = "test_key"
    
    deps = await get_api_dependencies(
        request_id=request_id,
        api_key=api_key,
        _=None,  # rate limit check
        settings=settings
    )
    
    assert deps["request_id"] == request_id
    assert deps["api_key"] == api_key
    assert deps["settings"] == settings
    assert "service" in deps