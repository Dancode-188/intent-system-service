import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.core.integration import ServiceIntegration
from app.core.clients import ServiceClientManager
from app.core.exceptions import ServiceError
from app.models import PredictionRequest

@pytest.fixture
def mock_client_manager(test_settings):
    """Mock client manager fixture with proper async support."""
    manager = ServiceClientManager(test_settings)
    
    # Use AsyncMock for async methods
    manager.context_client.get_context = AsyncMock()
    manager.intent_client.get_patterns = AsyncMock()
    manager.intent_client.analyze_intent = AsyncMock()
    
    return manager

@pytest.fixture
def service_integration(mock_client_manager):
    """Service integration fixture."""
    return ServiceIntegration(mock_client_manager)

@pytest.mark.asyncio
async def test_enrich_with_context(service_integration, test_prediction_request):
    """Test context enrichment."""
    context_data = {
        "embedding": [0.1, 0.2, 0.3],
        "metadata": {"source": "test"}
    }
    
    # Set async mock return value
    service_integration.clients.context_client.get_context.return_value = context_data
    
    features = test_prediction_request["features"]
    enriched = await service_integration._enrich_with_context(
        "test_context",
        features.copy()
    )
    
    assert enriched["context_embedding"] == context_data["embedding"]
    assert enriched["context_metadata"] == context_data["metadata"]
    service_integration.clients.context_client.get_context.assert_called_once_with("test_context")

@pytest.mark.asyncio
async def test_enrich_with_intent(service_integration, test_prediction_request):
    """Test intent enrichment."""
    intent_data = {
        "patterns": ["pattern1", "pattern2"],
        "metadata": {"confidence": 0.9}
    }
    service_integration.clients.intent_client.get_patterns.return_value = intent_data
    
    features = test_prediction_request["features"]
    enriched = await service_integration._enrich_with_intent(
        "test_user",
        features
    )
    
    assert "intent_patterns" in enriched
    assert enriched["intent_patterns"] == intent_data["patterns"]
    assert enriched["intent_metadata"] == intent_data["metadata"]

@pytest.mark.asyncio
@patch("app.core.integration.MetricsManager.update_service_health")
async def test_enrich_with_intent_error(mock_update_service_health, service_integration, test_prediction_request):
    """Test error handling in intent enrichment."""
    # Set up mock to raise generic exception 
    service_integration.clients.intent_client.get_patterns.side_effect = Exception("Generic error")
    
    features = test_prediction_request["features"]
    
    # Verify exception is propagated
    with pytest.raises(Exception) as exc_info:
        await service_integration._enrich_with_intent(
            "test_user",
            features
        )
    
    assert str(exc_info.value) == "Generic error"
    # Verify metrics were updated
    mock_update_service_health.assert_called_once_with("intent_service", False)

@pytest.mark.asyncio
async def test_enrich_prediction_request(service_integration, test_prediction_request):
    """Test full prediction request enrichment."""
    context_data = {
        "embedding": [0.1, 0.2, 0.3],
        "metadata": {"source": "test"}
    }
    intent_data = {
        "patterns": ["pattern1", "pattern2"],
        "metadata": {"confidence": 0.9}
    }
    
    service_integration.clients.context_client.get_context.return_value = context_data
    service_integration.clients.intent_client.get_patterns.return_value = intent_data
    
    request = PredictionRequest(**test_prediction_request)
    enriched = await service_integration.enrich_prediction_request(request)
    
    assert "context_embedding" in enriched
    assert "intent_patterns" in enriched
    assert enriched["context_metadata"] == context_data["metadata"]
    assert enriched["intent_metadata"] == intent_data["metadata"]

@pytest.mark.asyncio
async def test_analyze_prediction_result(service_integration):
    """Test prediction result analysis."""
    prediction_result = {
        "predictions": [{"action": "test", "probability": 0.9}],
        "confidence": 0.9,
        "metadata": {"type": "test"}
    }
    
    service_integration.clients.intent_client.analyze_intent.return_value = None
    
    await service_integration.analyze_prediction_result(
        "test_pred_id",
        prediction_result
    )
    
    service_integration.clients.intent_client.analyze_intent.assert_called_once()
    call_args = service_integration.clients.intent_client.analyze_intent.call_args[0][0]
    assert call_args["prediction_id"] == "test_pred_id"
    assert call_args["predictions"] == prediction_result["predictions"]

@pytest.mark.asyncio
async def test_service_error_handling(service_integration, test_prediction_request):
    """Test error handling in service integration."""
    service_integration.clients.context_client.get_context.side_effect = ServiceError("Test error")
    
    request = PredictionRequest(**test_prediction_request)
    enriched = await service_integration.enrich_prediction_request(request)
    
    # Should return original features on error
    assert enriched == request.features