# Intent Service Testing Guide

## Table of Contents
1. [Test Structure](#test-structure)
2. [Test Configuration](#test-configuration)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [Test Fixtures](#test-fixtures)
6. [Running Tests](#running-tests)
7. [Best Practices](#best-practices)

## Test Structure

```
tests/
├── integration/
│   ├── test_neo4j.py             # Neo4j integration tests
│   └── test_rate_limiter.py      # Rate limiter integration tests
├── unit/
│   ├── ml/
│   │   ├── bert/
│   │   │   └── test_model.py     # BERT model unit tests
│   │   ├── patterns/
│   │   │   ├── test_recognition.py # Pattern recognition tests
│   │   │   └── test_vector_store.py # Vector store tests
│   │   └── test_service.py       # ML service tests
│   ├── test_config.py            # Configuration tests
│   ├── test_connections.py       # Connection management tests
│   ├── test_dependencies.py      # Dependency injection tests
│   ├── test_health.py           # Health check tests
│   ├── test_metrics.py          # Metrics tests
│   └── test_models.py           # Data model tests
├── test_main.py                 # Main application tests
└── test_service.py              # Intent service tests
└── conftest.py                  # Shared test fixtures
```

## Test Configuration

### pytest Configuration
```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonfiles = test_*.py
python_classes = Test*
python_functions = test_*
filterwarnings = 
    ignore::DeprecationWarning
    ignore::UserWarning

markers =
    asyncio: mark test as an async test
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests

addopts =
    --verbose
    --cov=app
    --cov-report=term-missing
    --cov-report=html
```

### Test Dependencies

```python
# conftest.py
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
    return session

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    client = AsyncMock(spec=redis.Redis)
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    return client
```

## Unit Tests

### Configuration Tests (test_config.py)
```python
def test_validate_settings_valid():
    """Test validate_settings with valid settings"""
    settings = Settings(
        MAX_PATTERN_DEPTH=5,
        MIN_PATTERN_CONFIDENCE=0.5,
        RATE_LIMIT_WINDOW=60,
        NEO4J_POOL_SIZE=50
    )
    validate_settings(settings)

def test_validate_settings_invalid_pattern_depth():
    """Test validate_settings with invalid MAX_PATTERN_DEPTH"""
    settings = Settings(MAX_PATTERN_DEPTH=11)
    with pytest.raises(ValueError):
        validate_settings(settings)
```

### BERT Model Tests (test_model.py)
```python
@pytest.mark.asyncio
async def test_initialization(self, handler):
    """Test BERT handler initialization"""
    assert handler.is_initialized
    assert handler._model is not None
    assert handler._tokenizer is not None

@pytest.mark.asyncio
async def test_embedding_generation(self, handler):
    """Test generating embeddings for single text"""
    text = "test example text"
    embedding = await handler.generate_embedding(text)
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (768,)
```

### Pattern Recognition Tests (test_recognition.py)
```python
@pytest.mark.asyncio
async def test_store_pattern(self, recognizer, sample_pattern):
    """Test storing a new pattern"""
    result = await recognizer.store_pattern(sample_pattern)
    assert result["pattern_id"] == sample_pattern.id
    assert result["embedding_size"] == 768
    assert result["metadata"]["type"] == sample_pattern.type.value
```

## Integration Tests

### Neo4j Integration Tests (test_neo4j.py)
```python
@pytest.mark.integration
async def test_store_pattern(self, neo4j_handler):
    """Test storing pattern in Neo4j"""
    query = """
    CREATE (p:Pattern {
        id: $id,
        type: $type
    }) RETURN p
    """
    result = await neo4j_handler.execute_query(
        query,
        {"id": "test_123", "type": "sequential"}
    )
    assert result is not None
```

### Rate Limiter Tests (test_rate_limiter.py)
```python
@pytest.mark.integration
async def test_check_rate_limit_allowed(self, rate_limiter):
    """Test rate limit check when requests are allowed"""
    result = await rate_limiter.check_rate_limit(
        "test_client",
        "/api/test"
    )
    assert result["allowed"] is True
    assert result["current_requests"] == 50
    assert result["remaining_requests"] == 50
```

## Test Fixtures

### Common Fixtures
```python
@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock(spec=Request)
    request.app.state.settings = test_settings()
    return request

@pytest.fixture
def mock_intent_service(mock_neo4j_handler, test_settings):
    """Mock intent service for testing"""
    service = IntentService(test_settings)
    service.set_neo4j_handler(mock_neo4j_handler)
    return service
```

### ML Testing Fixtures
```python
@pytest.fixture
def mock_bert_handler():
    """Mock BERT handler"""
    handler = AsyncMock(spec=BERTHandler)
    handler.is_initialized = True
    test_vector = np.random.randn(768)
    
    async def async_generate_embedding(*args, **kwargs):
        return test_vector
        
    handler.generate_embedding.side_effect = async_generate_embedding
    return handler
```

## Running Tests

### Running All Tests
```bash
pytest
```

### Running Specific Test Types
```bash
# Run unit tests only
pytest tests/unit

# Run integration tests only
pytest tests/integration

# Run specific test file
pytest tests/unit/test_config.py

# Run with coverage report
pytest --cov=app --cov-report=html
```

## Best Practices

1. **Test Organization**
   - Keep unit tests and integration tests separate
   - Use appropriate markers for test types
   - Follow consistent naming conventions

2. **Async Testing**
   - Use `@pytest.mark.asyncio` for async tests
   - Properly mock async dependencies
   - Handle coroutines correctly

3. **Mocking**
   - Use appropriate mock types (MagicMock vs AsyncMock)
   - Mock at the correct level
   - Use fixtures for common mocks

4. **Test Coverage**
   - Maintain minimum 90% coverage
   - Test both success and error cases
   - Include edge cases

5. **Test Data**
   - Use fixtures for test data
   - Keep test data realistic
   - Clean up test data after tests

6. **Performance**
   - Keep tests focused and minimal
   - Use appropriate scoping for fixtures
   - Mock heavy dependencies

7. **Documentation**
   - Document test purposes
   - Include example usages
   - Explain complex test setups