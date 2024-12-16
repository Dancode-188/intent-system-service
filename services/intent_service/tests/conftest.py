import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Register markers to avoid warnings
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Mark test as a unit test")
    config.addinivalue_line("markers", "integration: Mark test as an integration test")
    config.addinivalue_line("markers", "e2e: Mark test as an end-to-end test")
    config.addinivalue_line("markers", "asyncio: Mark test as an async test")
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase, AsyncSession
import redis.asyncio as redis
from datetime import datetime

from app.main import app
from app.config import Settings, get_settings
from app.service import IntentService
from app.db.neo4j_handler import Neo4jHandler
from app.rate_limiter import EnhancedRateLimiter, RateLimitConfig

@pytest.fixture
def test_settings():
    """Test settings with test-specific values"""
    return Settings(
        NEO4J_URI="bolt://test:7687",
        NEO4J_USER="test",
        NEO4J_PASSWORD="test",
        REDIS_URL="redis://test:6379/0",
        RATE_LIMIT_WINDOW=60,
        MAX_REQUESTS_PER_WINDOW=100,
        DEBUG=True
    )

@pytest.fixture
def mock_neo4j_session():
    """Mock Neo4j session for testing"""
    session = AsyncMock(spec=AsyncSession)
    session.run = AsyncMock()
    session.close = AsyncMock()
    
    # Configure default return value for run
    session.run.return_value.single = AsyncMock(return_value={"result": "test"})
    session.run.return_value.data = AsyncMock(return_value=[{"result": "test"}])
    
    return session

@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for testing"""
    driver = AsyncMock(spec=AsyncGraphDatabase.driver)
    driver.session = AsyncMock()
    driver.verify_connectivity = AsyncMock()
    return driver

@pytest.fixture
def mock_neo4j_handler(mock_neo4j_driver, mock_neo4j_session, test_settings):
    """Mock Neo4j handler with configured session and driver"""
    handler = Neo4jHandler(test_settings)
    handler.driver = mock_neo4j_driver
    mock_neo4j_driver.session.return_value = mock_neo4j_session
    return handler

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    client = AsyncMock(spec=redis.Redis)
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.pipeline = AsyncMock(return_value=AsyncMock())
    return client

@pytest.fixture
def mock_rate_limiter(mock_redis_client):
    """Mock rate limiter for testing"""
    config = RateLimitConfig()
    limiter = EnhancedRateLimiter(mock_redis_client, config)
    return limiter

@pytest.fixture
def mock_intent_service(mock_neo4j_handler, test_settings):
    """Mock intent service for testing"""
    service = IntentService(test_settings)
    service.set_neo4j_handler(mock_neo4j_handler)
    return service

@pytest.fixture
def test_client(test_settings):
    """Test client for FastAPI app"""
    def get_test_settings():
        return test_settings
    
    app.dependency_overrides[get_settings] = get_test_settings
    
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_request_id():
    """Mock request ID for testing"""
    return "test_request_id"

@pytest.fixture
def sample_intent_data():
    """Sample intent data for testing"""
    return {
        "context_id": "ctx_123",
        "user_id": "user_789",
        "intent_data": {
            "action": "view_product",
            "embedding": [0.1, 0.2, 0.3],
            "confidence": 0.95
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@pytest.fixture
def sample_pattern_response():
    """Sample pattern response for testing"""
    return {
        "pattern_id": "pat_123",
        "pattern_type": "behavioral",
        "confidence": 0.85,
        "related_patterns": ["pat_456", "pat_789"],
        "metadata": {
            "patterns": ["pattern1", "pattern2"],
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_info": {
                "pattern_count": 2,
                "source": "test"
            }
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@pytest.fixture(autouse=True)
def mock_metrics():
    """Automatically mock metrics for all tests"""
    with patch('app.metrics.PATTERN_COUNT.labels') as mock_pattern_count, \
         patch('app.metrics.PATTERN_CONFIDENCE.labels') as mock_pattern_confidence, \
         patch('app.metrics.QUERY_DURATION.labels') as mock_query_duration, \
         patch('app.metrics.QUERY_ERRORS.labels') as mock_query_errors:
        
        mock_pattern_count.return_value.inc = MagicMock()
        mock_pattern_confidence.return_value.observe = MagicMock()
        mock_query_duration.return_value.observe = MagicMock()
        mock_query_errors.return_value.inc = MagicMock()
        
        yield {
            'pattern_count': mock_pattern_count,
            'pattern_confidence': mock_pattern_confidence,
            'query_duration': mock_query_duration,
            'query_errors': mock_query_errors
        }