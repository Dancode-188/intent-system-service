import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.ml.predictor import Predictor
from app.models import PredictionRequest, PredictionType
from app.core.exceptions import ModelError, ValidationError

@pytest.fixture
async def predictor(model, db_handler):
    """Predictor fixture."""
    return Predictor(
        model=model,
        db_handler=db_handler,
        max_predictions=5
    )

@pytest.mark.asyncio
async def test_generate_prediction(predictor, test_prediction_request):
    """Test prediction generation."""
    request = PredictionRequest(**test_prediction_request)
    
    response = await predictor.generate_prediction(request)
    
    assert response.prediction_id is not None
    assert len(response.predictions) <= predictor.max_predictions
    assert 0 <= response.confidence <= 1.0
    assert isinstance(response.timestamp, datetime)

@pytest.mark.asyncio
async def test_prediction_storage(predictor, test_prediction_request):
    """Test prediction storage in database."""
    request = PredictionRequest(**test_prediction_request)
    
    response = await predictor.generate_prediction(request)
    
    # Verify storage
    stored_prediction = await predictor.db.get_prediction(response.prediction_id)
    assert stored_prediction is not None
    assert stored_prediction["user_id"] == request.user_id
    # Instead of comparing exact values, verify confidence is within valid range
    assert 0 <= stored_prediction["confidence"] <= 1.0
    # Optionally verify it matches response confidence
    assert stored_prediction["confidence"] == response.confidence

@pytest.mark.asyncio
async def test_metric_storage(predictor, test_prediction_request):
    """Test metric storage functionality."""
    request = PredictionRequest(**test_prediction_request)
    
    response = await predictor.generate_prediction(request)
    
    # Verify metrics storage
    end_time = datetime.utcnow()
    start_time = datetime(2024, 1, 1)
    
    metrics = await predictor.db.get_metrics(
        start_time=start_time,
        end_time=end_time
    )
    
    assert len(metrics) > 0
    assert any(m["prediction_id"] == response.prediction_id for m in metrics)

@pytest.mark.asyncio
async def test_max_predictions_limit(predictor, test_prediction_request):
    """Test max predictions limit enforcement."""
    request = PredictionRequest(**test_prediction_request)
    
    response = await predictor.generate_prediction(request)
    
    assert len(response.predictions) <= predictor.max_predictions

@pytest.mark.asyncio
async def test_error_handling(predictor, test_prediction_request):
    """Test error handling in prediction generation."""
    # Simulate model error
    predictor.model.predict = MagicMock(side_effect=ModelError("Test error"))
    
    request = PredictionRequest(**test_prediction_request)
    
    with pytest.raises(ModelError):
        await predictor.generate_prediction(request)

@pytest.mark.asyncio
async def test_metric_storage_failure(predictor, test_prediction_request):
    """Test handling of metric storage failures."""
    request = PredictionRequest(**test_prediction_request)
    
    # Mock db.store_metric to fail
    predictor.db.store_metric = MagicMock(side_effect=Exception("Storage error"))
    
    # Should complete successfully despite metric storage failure
    response = await predictor.generate_prediction(request)
    assert response.prediction_id is not None

@pytest.mark.asyncio
async def test_general_prediction_error(predictor, test_prediction_request):
    """Test general error handling in prediction generation."""
    # Simulate generic error
    predictor.model.predict = MagicMock(side_effect=Exception("Unexpected error"))
    
    request = PredictionRequest(**test_prediction_request)
    
    with pytest.raises(ModelError) as exc_info:
        await predictor.generate_prediction(request)
    
    assert "Prediction generation failed: Unexpected error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_prediction(predictor, test_prediction_request):
    """Test prediction retrieval."""
    # First generate a prediction
    request = PredictionRequest(**test_prediction_request)
    response = await predictor.generate_prediction(request)
    
    # Then retrieve it
    stored = await predictor.get_prediction(response.prediction_id)
    
    assert stored is not None
    assert stored["prediction_id"] == response.prediction_id
    assert stored["user_id"] == request.user_id