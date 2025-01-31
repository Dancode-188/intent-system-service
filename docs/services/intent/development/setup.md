# Intent Service Development Guide

## Development Environment Setup

### Prerequisites

1. **Required Software**
   - Python 3.11+
   - Docker & Docker Compose
   - Neo4j 5.9.0+
   - Redis
   - Git

2. **Python Dependencies**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   .\venv\Scripts\activate   # Windows
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Development Tools**
   ```bash
   # Install development dependencies
   pip install -r requirements-dev.txt
   ```

## Local Development Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd intent-service
```

### 2. Environment Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit configuration for local development
INTENT_DEBUG=true
INTENT_NEO4J_URI=bolt://localhost:7687
INTENT_REDIS_URL=redis://localhost:6379/0
```

### 3. Start Dependencies
```bash
# Start Neo4j and Redis using Docker
docker-compose up -d neo4j redis
```

### 4. Run Service
```bash
# Run with auto-reload
uvicorn app.main:app --reload --port 8000
```

## Development Workflow

### 1. Code Style
```bash
# Format code
black app tests

# Sort imports
isort app tests

# Lint code
flake8 app tests
```

### 2. Type Checking
```bash
# Run type checker
mypy app
```

### 3. Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_service.py

# Run with coverage
pytest --cov=app

# Generate coverage report
pytest --cov=app --cov-report=html
```

### 4. Pre-commit Checks
```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit checks
pre-commit run --all-files
```

## Database Management

### Neo4j Setup
```bash
# Access Neo4j browser
open http://localhost:7474

# Default credentials
Username: neo4j
Password: development
```

### Redis CLI
```bash
# Access Redis CLI
docker exec -it intent-service_redis_1 redis-cli

# Monitor Redis
redis-cli monitor
```

## Testing

### 1. Unit Tests
```python
# Example test file: tests/test_service.py
import pytest
from app.service import IntentService

class TestIntentService:
    @pytest.fixture
    async def service(self):
        return IntentService()
    
    async def test_analyze_intent(self, service):
        result = await service.analyze_intent_pattern(
            "user_123",
            {"action": "view_product"}
        )
        assert result.pattern_id is not None
```

### 2. Integration Tests
```python
# Example integration test
@pytest.mark.integration
async def test_neo4j_connection(neo4j_handler):
    result = await neo4j_handler.execute_query(
        "RETURN 1 as value",
        {}
    )
    assert result.value == 1
```

### 3. Load Tests
```python
# Using locust for load testing
from locust import HttpUser, task

class IntentServiceUser(HttpUser):
    @task
    def analyze_intent(self):
        self.client.post("/api/v1/intent/analyze", 
            json={"user_id": "test", "action": "view"})
```

## Debugging

### 1. Debug Configuration
```python
# VSCode launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Intent Service",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "app.main:app",
                "--reload",
                "--port",
                "8000"
            ],
            "jinja": true,
            "justMyCode": false
        }
    ]
}
```

### 2. Logging
```python
# Configure debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Profiling

### 1. Code Profiling
```python
# Using cProfile
python -m cProfile -o output.prof app/main.py

# Analyze with snakeviz
snakeviz output.prof
```

### 2. Memory Profiling
```python
# Using memory_profiler
@profile
async def analyze_intent_pattern(self, user_id: str, data: dict):
    # Function code here
    pass
```

## Development Best Practices

### 1. Code Organization
```
app/
├── api/          # API endpoints
├── core/         # Core functionality
├── db/           # Database operations
├── ml/           # Machine learning components
├── models/       # Data models
└── utils/        # Utilities
```

### 2. Error Handling
```python
try:
    await operation()
except OperationError as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

### 3. Documentation
```python
def function_name(param: str) -> dict:
    """
    Function description.
    
    Args:
        param: Parameter description
        
    Returns:
        dict: Return value description
        
    Raises:
        ValueError: Error condition
    """
    pass
```

## Deployment for Testing

### 1. Build Docker Image
```bash
# Build service image
docker build -t intent-service .

# Run service
docker run -p 8000:8000 intent-service
```

### 2. Kubernetes Development
```yaml
# k8s/development.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: intent-service-dev
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: intent-service
          image: intent-service:dev
          env:
            - name: INTENT_DEBUG
              value: "true"
```

## Troubleshooting Guide

### 1. Common Issues

#### Database Connection
```python
# Check Neo4j connection
await neo4j_handler.verify_connectivity()

# Check Redis connection
await redis_client.ping()
```

#### Performance Issues
```python
# Enable detailed logging
logging.getLogger('app').setLevel(logging.DEBUG)
```

### 2. Debugging Tools
```bash
# Watch service logs
docker-compose logs -f intent-service

# Monitor metrics
curl localhost:8000/metrics
```