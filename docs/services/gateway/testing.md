# Gateway Testing Guide

## Testing Architecture

### Directory Structure
```
tests/
├── auth/                      # Authentication tests
│   ├── test_dependencies.py   # Auth dependency tests
│   ├── test_endpoints.py      # Auth endpoint tests
│   ├── test_security.py      # Security implementation tests
│   └── test_security_init.py # Security initialization tests
├── unit/
│   ├── core/                 # Core functionality tests
│   │   ├── circuit_breaker/  # Circuit breaker tests
│   │   └── services/        # Service integration tests
│   ├── discovery/           # Service discovery tests
│   │   └── test_registry.py
│   └── routing/             # Request routing tests
│       └── test_router.py
├── conftest.py              # Test configuration and fixtures
├── test_basic.py           # Basic sanity tests
├── test_main.py           # Main application tests
└── test_middleware.py     # Middleware tests
```

## Test Categories

### 1. Authentication Tests
- User authentication flow
- Token generation and validation
- Scope-based authorization
- User management

### 2. Circuit Breaker Tests
- State transitions
- Failure counting
- Recovery behavior
- Timeout handling

### 3. Service Discovery Tests
- Service registration
- Health checking
- Instance management
- Service deregistration

### 4. Routing Tests
- Route management
- Request proxying
- Circuit breaker integration
- Error handling

### 5. Middleware Tests
- Rate limiting
- CORS configuration
- Error handling
- Request processing

## Test Configuration

### Key Fixtures

```python
@pytest.fixture(scope="function")
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for our API."""
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="function")
def test_user() -> Dict[str, Any]:
    """Create a test user."""
    user = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "scopes": ["read", "write"]
    }
    return user

@pytest.fixture(scope="function")
def test_user_token(test_user: Dict[str, Any]) -> str:
    """Create a token for test user."""
    token = create_access_token(
        data={"sub": test_user["username"], "scopes": test_user["scopes"]}
    )
    return token
```

## Running Tests

### Basic Test Execution
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/auth/test_endpoints.py

# Run tests matching pattern
pytest -k "test_auth"
```

### Test Configuration
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = strict
addopts = -v --cov=src --cov-report=term-missing
```

## Component Testing

### 1. Circuit Breaker Testing
```python
@pytest.mark.asyncio
async def test_circuit_opens_after_failures(breaker, context):
    """Test circuit opens after threshold failures."""
    mock_func = AsyncMock(side_effect=Exception("Service error"))
    
    # Generate failures
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_func, context)
    
    assert breaker.state == CircuitState.OPEN
    assert breaker.stats.failed_requests == breaker.config.failure_threshold
```

### 2. Service Registry Testing
```python
@pytest.mark.asyncio
async def test_service_registration(registry, registration_request):
    """Test basic service registration."""
    instance = await registry.register_service(registration_request)
    
    assert instance.host == "localhost"
    assert instance.port == 8000
    assert instance.status == ServiceStatus.STARTING
```

### 3. Router Testing
```python
@pytest.mark.asyncio
async def test_proxy_request_success(router, route_definition, registry):
    """Test successful request proxying."""
    # Register service
    registration = RegistrationRequest(
        service_name="test_service",
        host="localhost",
        port=8000,
        check_endpoint="/health",
        check_interval=1
    )
    await registry.register_service(registration)
```

### 4. Authentication Testing
```python
@pytest.mark.asyncio
async def test_get_current_user_insufficient_scope():
    """Test get_current_user with insufficient permissions."""
    security_scopes = SecurityScopes(scopes=["admin"])
    token = create_access_token({
        "sub": "testuser",
        "scopes": ["read", "write"]
    })
```

## Mocking Strategies

### 1. Service Mocking
```python
@pytest.fixture
def mock_service():
    """Mock service responses."""
    with patch('httpx.AsyncClient.request') as mock:
        mock.return_value = AsyncMock(
            status_code=200,
            content=b"Success",
            headers={},
            aclose=AsyncMock()
        )
        yield mock
```

### 2. Redis Mocking
```python
@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = MagicMock()
    mock.pipeline.return_value = mock
    mock.execute.return_value = [True, 0, 5, True]
    return mock
```

## Test Coverage Requirements

### Minimum Coverage Targets
- Overall coverage: 90%
- Circuit breaker: 95%
- Authentication: 95%
- Request routing: 90%
- Service discovery: 90%
- Middleware: 85%

### Coverage Report
```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

## Writing New Tests

### Test Structure
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_new_feature():
    """Test description."""
    # Arrange
    # Set up test data and mocks
    
    # Act
    # Execute the functionality
    
    # Assert
    # Verify the results
```

### Best Practices
1. Use descriptive test names
2. Follow AAA pattern (Arrange-Act-Assert)
3. One assertion per test when possible
4. Mock external dependencies
5. Use fixtures for common setup
6. Include both positive and negative tests
7. Test edge cases and error conditions

## Continuous Integration

### GitHub Actions Configuration
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest --cov=src
```

## Test Maintenance

### Regular Tasks
1. Update test data and mocks
2. Review and update coverage targets
3. Clean up deprecated tests
4. Update test documentation
5. Review test performance

### Troubleshooting Tests
1. Check fixtures and mocks
2. Verify test isolation
3. Review error logs
4. Check timing-sensitive tests
5. Validate test data

## Need Help?

### Common Issues
1. Async test failures
   - Check for proper async/await usage
   - Verify event loop cleanup
2. Mocking issues
   - Verify mock setup
   - Check patch paths
3. Coverage gaps
   - Review uncovered lines
   - Add missing test cases

### Resources
- Project documentation
- Test logs
- Coverage reports
- CI/CD pipelines