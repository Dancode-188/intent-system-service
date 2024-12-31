import pytest
from fastapi import FastAPI, Depends, HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from prometheus_client import CollectorRegistry, REGISTRY
from starlette.responses import Response
from app.main import lifespan, create_application, metrics, health_check
from app.models import HealthResponse, PredictionRequest
from app.dependencies import get_api_dependencies
from app.core.connections import ConnectionManager

@pytest.mark.asyncio
async def test_lifespan():
    """Test application lifespan"""
    app = FastAPI()
    settings = MagicMock()
    
    # Mock the ConnectionManager directly
    with patch('app.main.get_settings', return_value=settings), \
         patch('app.main.ConnectionManager') as mock_cm:
        
        mock_instance = AsyncMock(spec=ConnectionManager)
        mock_cm.return_value = mock_instance
        
        async with lifespan(app):
            assert hasattr(app.state, "connections")
            assert hasattr(app.state, "settings")
            mock_instance.init.assert_called_once()
        
        mock_instance.close.assert_called_once()

@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint"""
    mock_service = AsyncMock()
    mock_service.health_check.return_value = {
        "status": "healthy",
        "components": {"db": "ok", "cache": "ok"}
    }
    
    mock_deps = {
        "service": mock_service,
        "settings": MagicMock(VERSION="1.0.0")
    }
    
    response = await health_check(mock_deps)
    assert isinstance(response, HealthResponse)
    assert response.status == "healthy"

@pytest.mark.asyncio
async def test_health_check_unhealthy():
    """Test health check when services are unhealthy"""
    mock_service = AsyncMock()
    mock_service.health_check.side_effect = Exception("Service unhealthy")
    
    mock_deps = {
        "service": mock_service,
        "settings": MagicMock(VERSION="1.0.0")
    }
    
    with pytest.raises(HTTPException) as exc:
        await health_check(mock_deps)
    assert exc.value.status_code == 503

@pytest.mark.asyncio
async def test_metrics():
    """Test metrics endpoint"""
    test_metrics = b"test_metrics"
    
    # Patch the generate_latest function in app.main
    with patch('app.main.generate_latest', return_value=test_metrics):
        response = await metrics()
        assert isinstance(response, Response)
        assert response.body == test_metrics

@pytest.mark.asyncio
async def test_process_prediction_error():
    """Test prediction processing error handling"""
    mock_service = AsyncMock()
    mock_service.process_prediction.side_effect = Exception("Processing failed")
    
    mock_deps = {
        "service": mock_service,
        "settings": MagicMock()
    }
    
    # Create test request using pydantic model
    request = PredictionRequest(
        user_id="test_user",
        context_id="test_context",
        prediction_type="short_term",
        features={"intent_patterns": [], "user_context": {}}
    )
    
    with pytest.raises(HTTPException) as exc:
        from app.main import generate_prediction  # Changed from process_prediction
        await generate_prediction(request, mock_deps)
    
    assert exc.value.status_code == 500
    assert "Error processing prediction" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_get_prediction_error():
    """Test prediction retrieval error handling"""
    mock_service = AsyncMock()
    mock_service.get_prediction_by_id.side_effect = Exception("Retrieval failed")
    
    mock_deps = {
        "service": mock_service,
        "settings": MagicMock()
    }
    
    with pytest.raises(HTTPException) as exc:
        from app.main import get_prediction
        await get_prediction("test_id", mock_deps)
    
    assert exc.value.status_code == 500
    assert "Error retrieving prediction" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_get_prediction_not_found():
    """Test prediction not found error"""
    mock_service = AsyncMock()
    mock_service.get_prediction_by_id.return_value = None
    
    mock_deps = {
        "service": mock_service,
        "settings": MagicMock()
    }
    
    with pytest.raises(HTTPException) as exc:
        from app.main import get_prediction
        await get_prediction("test_id", mock_deps)
    
    assert exc.value.status_code == 404
    assert "Prediction test_id not found" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_metrics_generation_error():
    """Test metrics generation error"""
    # Patch generate_latest to raise an exception
    with patch('app.main.generate_latest', side_effect=Exception("Metrics error")):
        with pytest.raises(HTTPException) as exc:
            await metrics()
        
        assert exc.value.status_code == 500
        assert "Error generating metrics" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_get_prediction_success():
    """Test successful prediction retrieval"""
    # Create mock prediction data
    mock_prediction = {
        "prediction_id": "test_id",
        "predictions": [{"action": "test_action", "probability": 0.85}],
        "confidence": 0.85,
        "metadata": {
            "model_version": "test",
            "prediction_type": "short_term",
            "timestamp": "2024-01-01T00:00:00",
        }
    }
    
    # Setup mock service
    mock_service = AsyncMock()
    mock_service.get_prediction_by_id.return_value = mock_prediction
    
    mock_deps = {
        "service": mock_service,
        "settings": MagicMock()
    }
    
    # Test the endpoint
    from app.main import get_prediction
    result = await get_prediction("test_id", mock_deps)
    
    # Verify result
    assert result == mock_prediction
    mock_service.get_prediction_by_id.assert_called_once_with("test_id")

def test_create_application():
    """Test FastAPI application creation"""
    app = create_application()

    # Retrieve middleware class names
    middleware_classes = [middleware.cls.__name__ for middleware in app.user_middleware]
    assert "TimingMiddleware" in middleware_classes
    assert "SecurityHeadersMiddleware" in middleware_classes
    assert "CORSMiddleware" in middleware_classes

    # Verify routes
    routes = {route.path for route in app.routes}
    assert "/health" in routes
    assert "/metrics" in routes
    assert "/api/v1/predict" in routes