# Prediction Service Development Guide

## Development Environment Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- TimescaleDB
- Redis
- Git

### Local Setup

1. **Clone the Repository**
```bash
git clone <repository-url>
cd prediction-service
```

2. **Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Set Up Environment Variables**
Create a `.env` file:
```env
# Service Configuration
PREDICTION_SERVICE_NAME=prediction-service
PREDICTION_VERSION=0.1.0
PREDICTION_DEBUG=true

# Database Configuration
PREDICTION_TIMESCALE_URL=postgresql://prediction_user:prediction_pass@localhost:5432/prediction_db
PREDICTION_TIMESCALE_POOL_SIZE=5

# Redis Configuration
PREDICTION_REDIS_URL=redis://localhost:6379/0
PREDICTION_REDIS_POOL_SIZE=5

# Model Configuration
PREDICTION_MODEL_PATH=./models
PREDICTION_CONFIDENCE_THRESHOLD=0.7
```

5. **Start Dependencies with Docker**
```bash
docker-compose up -d timescaledb redis
```

6. **Initialize Database**
```bash
# Wait for TimescaleDB to be ready
./scripts/healthcheck.sh

# Run database setup
./scripts/init.sh
```

## Development Workflow

### Code Organization
```
prediction-service/
├── app/
│   ├── core/           # Core functionality
│   │   ├── clients.py      # Service clients
│   │   ├── exceptions.py   # Custom exceptions
│   │   └── metrics.py      # Metrics collection
│   ├── db/            # Database handlers
│   ├── ml/            # ML models
│   └── service.py     # Main service logic
├── tests/            # Test suite
├── scripts/          # Utility scripts
└── models/           # ML model files
```

### Running the Service

1. **Development Mode**
```bash
uvicorn app.main:app --reload --port 8002
```

2. **Production Mode**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 4
```

### Testing

1. **Run All Tests**
```bash
pytest
```

2. **Run Specific Test Categories**
```bash
# Unit tests only
pytest tests/unit

# Integration tests
pytest tests/integration

# Test with coverage
pytest --cov=app --cov-report=html
```

3. **Test Configuration**
`pytest.ini` settings:
```ini
[pytest]
asyncio_mode = auto
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

4. **Example Test**
```python
@pytest.mark.asyncio
async def test_generate_prediction():
    """Test prediction generation"""
    request = PredictionRequest(
        user_id="test_user",
        context_id="test_context",
        prediction_type=PredictionType.SHORT_TERM,
        features={
            "intent_patterns": ["pattern1", "pattern2"],
            "user_context": {"location": "US", "device": "mobile"}
        }
    )
    
    response = await service.process_prediction(request)
    assert response.prediction_id is not None
    assert len(response.predictions) > 0
```

### Code Style

1. **Code Formatting**
Use Black for code formatting:
```bash
# Format code
black app tests

# Check formatting
black --check app tests
```

2. **Type Checking**
Use mypy for type checking:
```bash
mypy app
```

3. **Import Sorting**
Use isort for import sorting:
```bash
isort app tests
```

## Debugging

### Local Debugging

1. **Enable Debug Logging**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Debug Configuration**
```python
class Settings(BaseSettings):
    DEBUG: bool = True
    # ... other settings
```

3. **VSCode Launch Configuration**
`.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "app.main:app",
                "--reload",
                "--port",
                "8002"
            ],
            "jinja": true,
            "justMyCode": false
        }
    ]
}
```

### Database Debugging

1. **Connect to TimescaleDB**
```bash
psql -h localhost -U prediction_user -d prediction_db
```

2. **Check Tables**
```sql
\dt
SELECT * FROM predictions LIMIT 5;
SELECT * FROM prediction_metrics LIMIT 5;
```

### Redis Debugging

1. **Connect to Redis**
```bash
redis-cli
```

2. **Check Rate Limits**
```bash
KEYS "rate_limit:*"
GET "rate_limit:user123:/api/v1/predict"
```

## Common Issues and Solutions

### 1. Database Connection Issues
```python
# Check connection pool
async def check_db():
    try:
        await pool.fetchval('SELECT 1')
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
```

### 2. Model Loading Issues
```python
# Verify model path
if not Path(model_path).exists():
    raise FileNotFoundError(f"Model not found at {model_path}")
```

### 3. Rate Limiting Issues
```python
# Check rate limit configuration
print(rate_limiter.config.dict())
await rate_limiter.check_rate_limit("test_user", "/api/v1/predict")
```

## Integration Testing

### 1. Service Integration Tests
```python
@pytest.mark.integration
async def test_service_integration():
    """Test integration with other services"""
    client_manager = ServiceClientManager(settings)
    context_data = await client_manager.context_client.get_context("test_context")
    assert context_data is not None
```

### 2. Mock Services
```python
class MockContextService:
    async def get_context(self, context_id: str):
        return {
            "embedding": [0.1, 0.2, 0.3],
            "metadata": {"source": "test"}
        }
```

## CI/CD Pipeline

### GitHub Actions Workflow
`.github/workflows/main.yml`:
```yaml
name: CI/CD

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      timescaledb:
        image: timescale/timescaledb:latest-pg14
        env:
          POSTGRES_USER: prediction_user
          POSTGRES_PASSWORD: prediction_pass
          POSTGRES_DB: prediction_db
        ports:
          - 5432:5432
      redis:
        image: redis:latest
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run tests
        run: |
          pytest --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## API Development

### 1. Adding New Endpoints
```python
@router.post("/custom-predict")
async def custom_prediction(
    request: CustomPredictionRequest,
    deps: dict = Depends(get_api_dependencies)
):
    """Custom prediction endpoint"""
    return await deps["service"].process_custom_prediction(request)
```

### 2. Request Validation
```python
class CustomPredictionRequest(BaseModel):
    """Custom prediction request model"""
    user_id: str
    features: Dict[str, Any]
    
    @validator("features")
    def validate_features(cls, v):
        if "required_feature" not in v:
            raise ValueError("Missing required_feature")
        return v
```

## Performance Optimization

### 1. Database Optimization
```python
# Use connection pooling
pool = await asyncpg.create_pool(
    dsn=settings.TIMESCALE_URL,
    min_size=5,
    max_size=20,
    command_timeout=60
)

# Use prepared statements
stmt = await conn.prepare(
    'SELECT * FROM predictions WHERE user_id = $1'
)
```

### 2. Caching Strategy
```python
# Implement caching decorator
def cache_response(ttl: int = 300):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_key = f"cache:{func.__name__}:{args}:{kwargs}"
            # Check cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
            # Get fresh data
            result = await func(*args, **kwargs)
            # Cache result
            await redis.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
```

## Monitoring and Observability

### 1. Prometheus Metrics
```python
# Custom metrics
PREDICTION_DURATION = Histogram(
    'prediction_service_prediction_duration_seconds',
    'Time spent generating predictions',
    ['prediction_type']
)

# Track prediction duration
@PREDICTION_DURATION.time()
async def generate_prediction():
    # Prediction logic
    pass
```

### 2. Logging
```python
# Structured logging
logger = logging.getLogger(__name__)
logger.info(
    "Prediction generated",
    extra={
        "prediction_id": prediction_id,
        "user_id": user_id,
        "confidence": confidence
    }
)
```

## Contributing Guidelines

1. **Branch Naming**
   - Feature: `feature/description`
   - Bug Fix: `fix/description`
   - Documentation: `docs/description`

2. **Commit Messages**
   ```
   type(scope): description
   
   - type: feat, fix, docs, style, refactor, test, chore
   - scope: component affected
   - description: concise change description
   ```

3. **Pull Requests**
   - Create feature branch
   - Write tests
   - Update documentation
   - Request review
   - Address feedback
   - Merge when approved