# Gateway Development Guide

## Development Environment Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Redis 6.0+
- Git

### Initial Setup

1. Clone the Repository
```bash
git clone <repository-url>
cd isaas
```

2. Create Virtual Environment
```bash
# Create and activate virtual environment
python -m venv venv

# On Unix/macOS
source venv/bin/activate

# On Windows
.\venv\Scripts\activate
```

3. Install Dependencies
```bash
pip install -r requirements.txt
```

4. Environment Configuration
Create a `.env` file in the project root:
```env
# Application Settings
DEBUG=true
APP_NAME="Intent System Gateway"
API_V1_PREFIX="/api/v1"

# Security
SECRET_KEY="development-secret-key"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Service URLs (local development)
CONTEXT_SERVICE_URL="http://localhost:8001"
INTENT_SERVICE_URL="http://localhost:8002"
PREDICTION_SERVICE_URL="http://localhost:8003"
REALTIME_SERVICE_URL="http://localhost:8004"

# Redis Configuration
REDIS_HOST="localhost"
REDIS_PORT=6379

# Rate Limiting
RATE_LIMIT_PER_SECOND=10
```

5. Start Required Services
```bash
# Start Redis and other dependencies
docker-compose up -d redis
```

## Development Workflow

### Running the Gateway

1. Development Server
```bash
# Run with auto-reload
uvicorn src.main:app --reload --port 8000
```

2. Docker Development
```bash
# Build and run with Docker
docker-compose up --build gateway
```

### Code Organization

```
src/
├── auth/               # Authentication & authorization
│   ├── dependencies.py # Auth dependencies
│   ├── models.py      # Auth-related models
│   └── security.py    # Security implementations
├── core/              # Core functionality
│   ├── circuit_breaker/
│   └── services/
├── discovery/         # Service discovery
│   ├── registry.py
│   └── models.py
├── routing/           # Request routing
│   ├── router.py
│   └── models.py
├── config.py         # Configuration
├── main.py          # Application entry point
└── middleware.py    # Middleware implementations
```

### Development Best Practices

1. Code Style
   - Follow PEP 8 guidelines
   - Use type hints
   - Write descriptive docstrings
   - Keep functions focused and small

2. Git Workflow
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: your feature description"

# Push changes
git push origin feature/your-feature-name
```

3. Pre-commit Checks
```bash
# Run tests
pytest

# Check code formatting
black src/
isort src/

# Run type checking
mypy src/
```

### Adding New Features

1. Service Integration
```python
# Add service configuration in core/services/config.py
CORE_SERVICES: Dict[str, Dict[str, Any]] = {
    "new_service": {
        "service_name": "new_service",
        "path_prefix": f"{settings.API_V1_PREFIX}/new",
        "methods": ["GET", "POST"],
        "host": settings.NEW_SERVICE_URL.split("://")[1].split(":")[0],
        "port": int(settings.NEW_SERVICE_URL.split(":")[-1]),
        "check_endpoint": "/health",
        "check_interval": 30,
        "strip_prefix": True,
        "circuit_breaker": True,
        "rate_limit": True,
        "auth_required": True,
        "scopes": ["read", "write"]
    }
}
```

2. Adding Routes
```python
# Create route definition
route = RouteDefinition(
    service_name="new_service",
    path_prefix="/api/v1/new",
    methods=["GET", "POST"],
    strip_prefix=True,
    circuit_breaker=True,
    rate_limit=True,
    auth_required=True,
    scopes=["read", "write"]
)

# Register route
await router.add_route(route)
```

### Debugging

1. Enable Debug Logging
```python
# In your .env file
DEBUG=true

# In code
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
```

2. Debug Tools
```python
# Use FastAPI's debug middleware
from fastapi.middleware.debugging import DebugMiddleware
app.add_middleware(DebugMiddleware)

# Add request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    return response
```

3. Circuit Breaker Debugging
```python
# Enable circuit breaker logging
logger.debug(
    f"Circuit {self.name} state change: {old_state} -> {self.state}"
)
```

### Common Development Tasks

1. Adding New Dependencies
```bash
# Add to requirements.txt
pip install new-package
pip freeze > requirements.txt
```

2. Database Migrations (if needed)
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

3. Running Specific Tests
```bash
# Run specific test file
pytest tests/test_specific.py

# Run tests with specific marker
pytest -m "integration"

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

### Development Tools

1. API Documentation
   - Access Swagger UI: http://localhost:8000/docs
   - Access ReDoc: http://localhost:8000/redoc

2. Monitoring
   - Prometheus metrics: http://localhost:8000/metrics
   - Health check: http://localhost:8000/health

3. Debug Tools
   - Redis Commander: http://localhost:8081
   - Grafana (if configured): http://localhost:3000

## Troubleshooting Common Issues

1. Redis Connection Issues
```python
# Check Redis connection
redis-cli ping
redis-cli info
```

2. Service Discovery Problems
```bash
# Check service health
curl http://localhost:8000/health

# Check service registry
curl http://localhost:8000/api/v1/services
```

3. Authentication Issues
```bash
# Generate test token
curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=testpass"
```

## Need Help?

1. Check the logs:
```bash
docker-compose logs gateway
```

2. Review error patterns:
```python
logger.error(
    f"Error in {function_name}",
    exc_info=True,
    extra={"context": context}
)
```

3. Contact the team:
   - Create an issue in the repository
   - Tag appropriate team members
   - Include relevant logs and context