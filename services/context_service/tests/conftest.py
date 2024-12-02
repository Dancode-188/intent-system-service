import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from app.config import Settings
from app.service import ContextService
from app.dependencies import RateLimiter

@pytest.fixture
def settings():
    return Settings()

@pytest.fixture
def service(settings):
    return ContextService(settings)

@pytest.fixture
def mock_redis():
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.incr.return_value = 1
    return redis_mock

@pytest.fixture
def rate_limiter(mock_redis):
    return RateLimiter(mock_redis)

@pytest.fixture
def mock_rate_limiter():
    limiter = AsyncMock()
    limiter.check_rate_limit.return_value = True
    return limiter

@pytest.fixture
def valid_request_data():
    return {
        "user_id": "test_user",
        "action": "view_product",
        "context": {
            "product_id": "123",
            "category": "electronics",
            "price": 999.99
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@pytest.fixture
def valid_headers():
    return {
        "X-API-Key": "test_api_key",
        "X-Request-ID": "test_request_id"
    }

# Configure pytest-asyncio
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )