# Context Service Testing Guide

## Overview

This guide details the testing strategy and implementation for the Context Service. The service uses pytest as its primary testing framework, with additional tools for specific testing needs.

## Test Structure

```
tests/
├── conftest.py            # Shared test fixtures
├── unit/
│   ├── test_service.py    # Service unit tests
│   ├── test_models.py     # Data models tests
│   └── test_ml.py        # ML component tests
├── integration/
│   ├── test_api.py       # API integration tests
│   └── test_redis.py     # Redis integration tests
└── performance/
    └── test_load.py      # Load and performance tests
```

## Test Configuration

### pytest Configuration

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test markers
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    slow: Slow running tests

# Test options
addopts =
    -v
    --cov=app
    --cov-report=term-missing
    --cov-report=html
```

### Coverage Configuration

```ini
# .coveragerc
[run]
source = app
omit =
    */tests/*
    */migrations/*
    */config.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if __name__ == .__main__.:
    raise NotImplementedError
```

## Fixtures

```python
# conftest.py
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from app.config import Settings
from app.service import ContextService

@pytest.fixture
def settings():
    """Test settings fixture"""
    return Settings(
        SERVICE_NAME="test-service",
        DEBUG=True,
        MODEL_NAME="distilbert-base-uncased",
        MAX_SEQUENCE_LENGTH=512
    )

@pytest.fixture
def service(settings):
    """Context service fixture"""
    return ContextService(settings)

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.incr.return_value = 1
    return redis_mock

@pytest.fixture
def valid_request_data():
    """Valid request data fixture"""
    return {
        "user_id": "test_user",
        "action": "view_product",
        "context": {
            "product_id": "123",
            "category": "electronics"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
```

## Unit Testing

### Service Tests

```python
# tests/unit/test_service.py
import pytest
from app.service import ContextService
import numpy as np

@pytest.mark.asyncio
async def test_generate_embedding(service, valid_request_data):
    """Test embedding generation"""
    # Create context text
    context_text = f"{valid_request_data['action']} {service._format_context(valid_request_data['context'])}"
    
    # Generate embedding
    embedding = await service.generate_embedding(context_text)
    
    # Verify embedding
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (768,)
    assert not np.isnan(embedding).any()

@pytest.mark.asyncio
async def test_process_context(service, valid_request_data):
    """Test context processing"""
    response = await service.process_context(valid_request_data)
    
    assert response.context_id.startswith("ctx_")
    assert isinstance(response.embedding, list)
    assert len(response.embedding) == 768
    assert 0 <= response.confidence <= 1
    assert response.action_type in ["exploration", "search", "transaction", "other"]
```

### Model Tests

```python
# tests/unit/test_models.py
import pytest
from app.models import ContextRequest, ContextResponse
from datetime import datetime

def test_context_request_validation():
    """Test ContextRequest validation"""
    # Valid request
    request = ContextRequest(
        user_id="test_user",
        action="view_product",
        context={"product_id": "123"},
        timestamp=datetime.utcnow()
    )
    assert request.user_id == "test_user"
    
    # Invalid request
    with pytest.raises(ValueError):
        ContextRequest(
            user_id="",  # Empty user_id
            action="view_product"
        )
```

## Integration Testing

### API Tests

```python
# tests/integration/test_api.py
from fastapi.testclient import TestClient
from app.main import app

def test_context_api_endpoint(client, valid_request_data, valid_headers):
    """Test context analysis endpoint"""
    response = client.post(
        "/api/v1/context",
        json=valid_request_data,
        headers=valid_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "context_id" in data
    assert "embedding" in data
    assert "confidence" in data
    assert "action_type" in data
    assert "processed_timestamp" in data

def test_rate_limiting(client, valid_request_data, valid_headers):
    """Test rate limiting"""
    # Send requests up to limit
    for _ in range(100):
        response = client.post(
            "/api/v1/context",
            json=valid_request_data,
            headers=valid_headers
        )
        assert response.status_code == 200
    
    # Next request should be rate limited
    response = client.post(
        "/api/v1/context",
        json=valid_request_data,
        headers=valid_headers
    )
    assert response.status_code == 429
```

## Performance Testing

```python
# tests/performance/test_load.py
import asyncio
import time
from locust import HttpUser, task, between

class ContextServiceUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def analyze_context(self):
        """Test context analysis under load"""
        self.client.post(
            "/api/v1/context",
            json={
                "user_id": "test_user",
                "action": "view_product",
                "context": {"product_id": "123"}
            },
            headers={"X-API-Key": "test_key"}
        )

# Run with: locust -f tests/performance/test_load.py
```

## Test Data Management

### Test Data Generation

```python
# tests/utils/data_generator.py
import random
from datetime import datetime, timedelta

def generate_test_data(num_samples: int = 100) -> list:
    """Generate test data samples"""
    actions = ["view_product", "search", "add_to_cart", "purchase"]
    categories = ["electronics", "books", "clothing", "food"]
    
    return [
        {
            "user_id": f"user_{i}",
            "action": random.choice(actions),
            "context": {
                "product_id": f"prod_{random.randint(1, 1000)}",
                "category": random.choice(categories),
                "price": round(random.uniform(10, 1000), 2)
            },
            "timestamp": (
                datetime.utcnow() - timedelta(days=random.randint(0, 30))
            ).isoformat()
        }
        for i in range(num_samples)
    ]
```

## CI/CD Pipeline Testing

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Best Practices

### 1. Test Organization
- Group tests by type (unit, integration, performance)
- Use meaningful test names
- Follow AAA pattern (Arrange, Act, Assert)
- Keep tests focused and small

### 2. Mocking
```python
# Example of proper mocking
@pytest.mark.asyncio
async def test_redis_integration(mocker):
    # Mock Redis client
    mock_redis = mocker.patch('redis.Redis')
    mock_redis.get.return_value = "cached_value"
    
    # Use mock in test
    result = await redis_handler.get_value("key")
    assert result == "cached_value"
```

### 3. Test Coverage
- Aim for >90% coverage
- Focus on critical paths
- Document uncovered code
- Use meaningful assertions

### 4. Performance Testing
- Set baseline metrics
- Test under various loads
- Monitor resource usage
- Test error scenarios

## Troubleshooting

### Common Issues

1. **Async Test Failures**
```python
# Use proper async fixtures
@pytest.fixture
async def async_client():
    async with AsyncClient() as client:
        yield client
```

2. **Memory Issues**
```python
# Clean up resources
@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Cleanup code here
```

3. **Slow Tests**
```python
# Mark slow tests
@pytest.mark.slow
def test_slow_operation():
    # Slow test code here
```

## Test Monitoring

### Coverage Reports
```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# Generate XML coverage report
pytest --cov=app --cov-report=xml
```

### Performance Metrics
```python
# Record test execution times
@pytest.mark.benchmark
def test_performance(benchmark):
    benchmark(lambda: service.some_operation())
```