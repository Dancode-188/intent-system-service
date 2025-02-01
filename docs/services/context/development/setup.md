# Context Service Development Setup Guide

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Git
- Poetry (recommended) or pip
- Visual Studio Code (recommended)

## Local Development Setup

### 1. Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd context-service

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Using pip
pip install -r requirements.txt
```

### 3. Development Dependencies

```bash
# Install development dependencies
pip install -r requirements-dev.txt
```

### 4. Environment Configuration

Create a `.env.development` file:

```ini
# Service Configuration
CONTEXT_DEBUG=true
CONTEXT_SERVICE_NAME=context-service-dev
CONTEXT_VERSION=0.1.0

# ML Model Configuration
CONTEXT_MODEL_NAME=distilbert-base-uncased
CONTEXT_MAX_SEQUENCE_LENGTH=512
CONTEXT_BATCH_SIZE=32

# Privacy Settings
CONTEXT_PRIVACY_EPSILON=0.1
CONTEXT_PRIVACY_DELTA=1e-5

# Monitoring
CONTEXT_ENABLE_METRICS=true
CONTEXT_METRICS_PORT=8000
```

### 5. Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
    -   id: trailing-whitespace
    -   id: end-of-file-fixer
    -   id: check-yaml
    -   id: check-added-large-files

-   repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
    -   id: black

-   repo: https://github.com/PyCQA/flake8
    rev: 6.1.0
    hooks:
    -   id: flake8

-   repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
    -   id: isort
```

## Docker Development Environment

### 1. Docker Setup

Create `docker-compose.dev.yml`:

```yaml
version: '3.8'

services:
  context-service:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - CONTEXT_DEBUG=true
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

Create `Dockerfile.dev`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### 2. Start Development Environment

```bash
# Start services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

## IDE Setup

### Visual Studio Code

1. Install Extensions:
   - Python
   - Pylance
   - Docker
   - YAML
   - GitLens
   - Python Test Explorer

2. Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.testing.nosetestsEnabled": false
}
```

## Testing Setup

### 1. Test Configuration

Create `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --cov=app
    --cov-report=term-missing
    --cov-report=html
```

### 2. Test Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

### 3. Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_service.py

# Run with coverage report
pytest --cov=app --cov-report=html
```

## Development Workflow

### 1. Branch Strategy

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Create bugfix branch
git checkout -b bugfix/bug-description
```

### 2. Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Run linter
flake8

# Run type checker
mypy .
```

### 3. Testing

```bash
# Run tests before commit
pytest

# Run specific test with verbose output
pytest tests/test_service.py -v
```

## Debugging

### 1. Local Debugging

```python
# main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        debug=True
    )
```

### 2. VSCode Debug Configuration

Create `.vscode/launch.json`:

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
                "8000"
            ],
            "jinja": true,
            "justMyCode": true
        },
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        }
    ]
}
```

## Common Development Tasks

### 1. Adding Dependencies

```bash
# Using Poetry
poetry add package-name

# Using pip
pip install package-name
pip freeze > requirements.txt
```

### 2. Database Migrations

```bash
# Not applicable for current version as we use Redis
# Template for future SQL database migrations
```

### 3. API Documentation

```bash
# Access OpenAPI docs
http://localhost:8000/docs

# Access ReDoc
http://localhost:8000/redoc
```

## Troubleshooting

### 1. Common Issues

- **Model Download Issues**
  ```bash
  # Clear cached models
  rm -rf ~/.cache/huggingface/
  ```

- **Redis Connection Issues**
  ```bash
  # Check Redis connection
  redis-cli ping
  ```

- **Docker Issues**
  ```bash
  # Remove containers and volumes
  docker-compose down -v
  # Rebuild images
  docker-compose build --no-cache
  ```

### 2. Logging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Best Practices

1. **Code Style**
   - Follow PEP 8
   - Use type hints
   - Write docstrings
   - Keep functions small

2. **Testing**
   - Write tests first
   - Maintain high coverage
   - Use meaningful assertions
   - Mock external services

3. **Git Commits**
   - Write clear commit messages
   - Keep commits focused
   - Squash before merging
   - Reference issues

4. **Documentation**
   - Update docs with changes
   - Include examples
   - Document edge cases
   - Keep README updated