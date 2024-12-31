import pytest
import asyncio
from typing import AsyncGenerator, Dict, Any
from httpx import AsyncClient
from datetime import datetime
import redis.asyncio as redis
from fastapi import FastAPI
from unittest.mock import AsyncMock, patch, MagicMock
import os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import uuid

from app.config import Settings, get_settings
from app.core.connections import ConnectionManager
from app.core.integration import ServiceIntegration
from app.core.exceptions import ModelError
from app.main import app
from app.ml.models import PredictionModel
from app.db.timescale import TimescaleDBHandler

@pytest.fixture
def test_settings() -> Settings:
    """Test settings with test-specific configurations."""
    return Settings(
        TIMESCALE_URL="postgresql://prediction_user:prediction_pass@localhost:5432/prediction_test_db",
        REDIS_URL="redis://localhost:6379/1",  # Use different DB for testing
        MODEL_PATH="tests/test_models",
        DEBUG=True
    )

@pytest.fixture
async def test_app(test_settings) -> AsyncGenerator[FastAPI, None]:
    """Test app fixture with test configurations."""
    app.state.settings = test_settings
    app.state.connections = ConnectionManager(test_settings)
    await app.state.connections.init()
    
    yield app
    
    await app.state.connections.close()

@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Test client fixture."""
    async with AsyncClient(
        app=test_app,
        base_url="http://test",
        headers={"X-API-Key": "test_api_key"}
    ) as client:
        yield client

@pytest.fixture
async def db_handler(test_settings, mock_pool) -> AsyncGenerator[TimescaleDBHandler, None]:
    """Database handler fixture with mocked pool."""
    pool, _ = mock_pool
    handler = TimescaleDBHandler(test_settings)
    
    # Patch pool creation
    with patch('asyncpg.create_pool', AsyncMock(return_value=pool)):
        await handler.initialize()
        yield handler
        await handler.close()

@pytest.fixture
async def redis_client(test_settings) -> AsyncGenerator[redis.Redis, None]:
    """Redis client fixture."""
    client = redis.Redis.from_url(test_settings.REDIS_URL)
    yield client
    await client.flushdb()  # Clean test data
    await client.close()

@pytest.fixture
def test_prediction_request() -> Dict[str, Any]:
    """Sample prediction request data."""
    return {
        "user_id": "test_user",
        "context_id": "test_context",
        "prediction_type": "short_term",
        "features": {
            "intent_patterns": ["pattern1", "pattern2"],
            "user_context": {
                "location": "US",
                "device": "mobile"
            }
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@pytest.fixture
async def model(test_settings) -> AsyncGenerator[PredictionModel, None]:
    """Model fixture with mocked predictions."""
    model = PredictionModel(
        model_path=test_settings.MODEL_PATH,
        confidence_threshold=0.5,
        use_scaler=True  # Explicitly set to True
    )
    
    # Create mock model object
    mock_model = MagicMock()
    mock_model.predict_proba = MagicMock(return_value=np.array([[0.85, 0.15]]))
    mock_model.classes_ = np.array(["test_action", "other_action"])
    
    # Create mock scaler object
    mock_scaler = MagicMock()
    mock_scaler.transform = MagicMock(return_value=np.array([[1.0, 2.0]]))
    
    # Set up model internals
    model.model = mock_model
    model.scaler = mock_scaler  # Add this line
    model._initialized = True
    
    # Rest of the fixture remains the same...
    async def mock_predict(*args, **kwargs):
        if not model._initialized:
            raise ModelError("Model not initialized")
        model._validate_features(kwargs.get('features', {}))
        
        return {
            "predictions": [
                {"action": "test_action", "probability": 0.85}
            ],
            "confidence": 0.85,
            "metadata": {
                "model_version": "test", 
                "prediction_type": kwargs.get('prediction_type', 'short_term'),
                "timestamp": datetime.utcnow().isoformat(),
                "feature_count": 4
            }
        }
    
    model.predict = mock_predict
    
    yield model
    
    await model.close()

@pytest.fixture(autouse=True)
async def test_cleanup():
    """Cleanup resources after each test."""
    yield
    await asyncio.sleep(0)
    tasks = [t for t in asyncio.all_tasks() 
             if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)

@pytest.fixture(autouse=True)
def mock_uuid():
    # Force the predictor to generate the same prediction_id each time
    with patch("uuid.uuid4", return_value=uuid.UUID("00000000-0000-0000-0000-baf4795f0000")):
        yield

@pytest.fixture
def mock_clients():
    """Mock service clients with proper async support."""
    mock_manager = AsyncMock()
    
    # Setup context client
    context_client = AsyncMock()
    context_client.get_context = AsyncMock()
    mock_manager.context_client = context_client
    
    # Setup intent client
    intent_client = AsyncMock()
    intent_client.get_patterns = AsyncMock()
    intent_client.analyze_intent = AsyncMock()
    mock_manager.intent_client = intent_client
    
    return mock_manager

@pytest.fixture
def service_integration(mock_clients):
    """Service integration fixture with mocked clients."""
    return ServiceIntegration(mock_clients)

@pytest.fixture
async def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    
    # Store prediction and metric data
    store = {
        "predictions": {},
        "metrics": []
    }
    
    async def execute_mock(*args, **kwargs):
        if "CREATE TABLE" in args[0]:
            return
        
        if "INSERT INTO predictions" in args[0]:
            # Store prediction data
            prediction_data = {
                "prediction_id": args[1],
                "user_id": args[2],
                "context_id": args[3],
                "prediction_type": args[4],
                "predictions": args[5],
                "confidence": args[6],
                "metadata": args[7],
                "created_at": args[8]
            }
            store["predictions"][args[1]] = prediction_data
            
        elif "INSERT INTO prediction_metrics" in args[0]:
            # Store metric data
            metric_data = {
                "time": args[1],
                "prediction_id": args[2],
                "metric_name": args[3],
                "metric_value": args[4],
                "tags": args[5]
            }
            store["metrics"].append(metric_data)

    async def fetchrow_mock(*args, **kwargs):
        if "predictions" in args[0]:
            prediction_id = args[1]
            return store["predictions"].get(prediction_id)
        return None

    async def fetch_mock(*args, **kwargs):
        if "prediction_metrics" in args[0]:
            return store["metrics"]
        elif "predictions" in args[0] and "user_id" in args[0]:
            # Handle historical predictions query
            return [v for v in store["predictions"].values() 
                   if v["user_id"] == args[1] and 
                   args[2] <= v["created_at"] <= args[3]]
        return []

    # Set up mock behavior
    conn.execute = AsyncMock(side_effect=execute_mock)
    conn.fetchrow = AsyncMock(side_effect=fetchrow_mock)
    conn.fetch = AsyncMock(side_effect=fetch_mock)
    
    # Connection context manager
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire.return_value = cm
    pool.close = AsyncMock()

    return pool, conn