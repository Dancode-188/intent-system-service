import pytest
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from app.service import PredictionService
from app.models import PredictionRequest, PredictionType
from app.core.exceptions import ModelError, ValidationError, ServiceError
from app.config import Settings

@pytest.fixture
def test_settings() -> Settings:
    """Test settings with test-specific configurations."""
    return Settings(
        TIMESCALE_URL="postgresql://prediction_user:prediction_pass@localhost:5432/prediction_test_db",
        REDIS_URL="redis://localhost:6379/1",
        MODEL_PATH="tests/test_models",  # Keep this path
        DEBUG=True
    )

@pytest.fixture
async def prediction_service(test_settings, db_handler, model):  # Add model dependency
    """Prediction service fixture."""
    service = PredictionService(test_settings)
    service.model = model  # Set the already initialized model
    service.set_db_handler(db_handler)
    await service.initialize()
    yield service
    await service.close()

@pytest.mark.asyncio
async def test_service_initialization(prediction_service):
    """Test service initialization."""
    assert prediction_service._initialized
    assert prediction_service.model is not None
    assert prediction_service.predictor is not None
    assert prediction_service.client_manager is not None
    assert prediction_service.service_integration is not None

@pytest.mark.asyncio
async def test_process_prediction(prediction_service, test_prediction_request):
    """Test prediction processing."""
    # Mock service integration responses
    prediction_service.service_integration.enrich_prediction_request = AsyncMock(
        return_value={
            "intent_patterns": ["pattern1", "pattern2"],
            "user_context": {"location": "US", "device": "mobile"},
            "enriched_feature1": 1.0,
            "enriched_feature2": 1.0
        }
    )
    prediction_service.service_integration.analyze_prediction_result = AsyncMock()
    
    request = PredictionRequest(**test_prediction_request)
    response = await prediction_service.process_prediction(request)
    
    assert response.prediction_id is not None
    assert len(response.predictions) > 0
    assert 0 <= response.confidence <= 1.0
    assert response.metadata is not None

@pytest.mark.asyncio
async def test_batch_predictions(prediction_service, test_prediction_request):
    """Test batch prediction processing."""
    requests = [
        PredictionRequest(**test_prediction_request),
        PredictionRequest(**test_prediction_request)
    ]
    
    responses = await prediction_service.process_batch_predictions(requests)
    
    assert len(responses) == 2
    for response in responses:
        assert response.prediction_id is not None
        assert len(response.predictions) > 0

@pytest.mark.asyncio
async def test_historical_analysis(prediction_service, test_prediction_request):
    """Test historical analysis functionality."""
    # First generate some predictions
    request = PredictionRequest(**test_prediction_request)
    await prediction_service.process_prediction(request)
    
    # Get historical analysis
    analysis = await prediction_service.get_historical_analysis(
        user_id=request.user_id,
        start_time=datetime(2024, 1, 1),
        end_time=datetime.utcnow()
    )
    
    assert analysis["prediction_count"] > 0
    assert "average_confidence" in analysis
    assert "metrics" in analysis
    assert "predictions" in analysis

@pytest.mark.asyncio
async def test_error_handling(prediction_service, test_prediction_request, test_settings):
    """Test service error handling."""
    # Test uninitialized service
    uninit_service = PredictionService(test_settings)
    with pytest.raises(ValidationError):
        await uninit_service.process_prediction(
            PredictionRequest(**test_prediction_request)
        )
    
    # Test model error
    prediction_service.predictor.model.predict = MagicMock(
        side_effect=ModelError("Test error")
    )
    with pytest.raises(ModelError):
        await prediction_service.process_prediction(
            PredictionRequest(**test_prediction_request)
        )

@pytest.mark.asyncio
async def test_service_cleanup(prediction_service):
    """Test service cleanup."""
    await prediction_service.close()
    
    assert not prediction_service._initialized
    assert prediction_service.model is None
    assert prediction_service.predictor is None

@pytest.mark.asyncio
async def test_request_validation(prediction_service):
    """Test request validation failures."""
    # Start with valid request
    valid_request = PredictionRequest(
        user_id="test_user",  # Add required user_id
        context_id="test",
        prediction_type=PredictionType.SHORT_TERM,
        features={"intent_patterns": [], "user_context": {}}
    )

    # Test empty user_id
    request_no_user = valid_request.model_copy()
    request_no_user.user_id = ""  # Empty string
    with pytest.raises(ValidationError, match="Missing user_id"):
        prediction_service._validate_request(request_no_user)

    # Test missing context_id
    request_no_context = valid_request.model_copy()
    request_no_context.context_id = ""
    with pytest.raises(ValidationError, match="Missing context_id"):
        prediction_service._validate_request(request_no_context)

    # Test missing features
    with pytest.raises(ValidationError, match="Missing features"):
        await prediction_service.process_prediction(
            PredictionRequest(
                user_id="test",
                context_id="test",
                prediction_type=PredictionType.SHORT_TERM,
                features={}
            )
        )
    
    # Test missing required features
    with pytest.raises(ValidationError, match="Missing required features"):
        await prediction_service.process_prediction(
            PredictionRequest(
                user_id="test",
                context_id="test",
                prediction_type=PredictionType.SHORT_TERM,
                features={"other_feature": "value"}
            )
        )

    # Test missing user_id using service method directly
    with pytest.raises(ValidationError, match="Missing user_id"):
        prediction_service._validate_request(
            PredictionRequest(
                user_id="",  # Empty user_id
                context_id="test",
                prediction_type=PredictionType.SHORT_TERM,
                features={"intent_patterns": [], "user_context": {}}
            )
        )

@pytest.mark.asyncio
async def test_process_prediction_errors(prediction_service, test_prediction_request):
    """Test prediction processing error cases."""
    request = PredictionRequest(**test_prediction_request)
    
    # Mock the integration method properly
    prediction_service.service_integration = AsyncMock()
    prediction_service.service_integration.enrich_prediction_request.side_effect = ServiceError("Integration error")

    with pytest.raises(ServiceError, match="Integration error"):
        await prediction_service.process_prediction(request)

    # Test unexpected error
    prediction_service.service_integration.enrich_prediction_request.side_effect = Exception("Unexpected error")
    with pytest.raises(ModelError, match="Prediction processing failed"):
        await prediction_service.process_prediction(request)

@pytest.mark.asyncio
async def test_batch_prediction_errors(prediction_service, test_prediction_request):
    """Test batch prediction error cases."""
    requests = [PredictionRequest(**test_prediction_request) for _ in range(2)]
    
    # Create proper mock response
    mock_response = MagicMock()
    mock_response.prediction_id = "test_id"
    mock_response.predictions = []
    mock_response.confidence = 0.5

    # Mock predictor with proper async behavior
    prediction_service.predictor = AsyncMock()
    prediction_service.predictor.generate_prediction.side_effect = [
        ModelError("Test error"),  # First request fails
        ModelError("Test error")   # Second request fails
    ]

    with pytest.raises(ModelError, match="Batch processing failed"):
        await prediction_service.process_batch_predictions(requests)

@pytest.mark.asyncio
async def test_historical_analysis_errors(prediction_service):
    """Test historical analysis error cases."""
    # Test uninitialized service
    prediction_service._initialized = False
    with pytest.raises(ValidationError, match="Service not initialized"):
        await prediction_service.get_historical_analysis(
            user_id="test",
            start_time=datetime(2024, 1, 1),
            end_time=datetime.utcnow()
        )

    # Setup proper mocks
    prediction_service._initialized = True
    prediction_service.db_handler = AsyncMock()
    prediction_service.db_handler.get_historical_predictions = AsyncMock()
    prediction_service.db_handler.get_historical_predictions.side_effect = Exception("DB error")

    with pytest.raises(Exception, match="DB error"):
        await prediction_service.get_historical_analysis(
            user_id="test",
            start_time=datetime(2024, 1, 1),
            end_time=datetime.utcnow()
        )

@pytest.mark.asyncio
async def test_service_cleanup_errors(prediction_service):
    """Test service cleanup error cases."""
    # Setup proper mocks
    prediction_service.model = AsyncMock()
    prediction_service.predictor = AsyncMock()
    prediction_service.predictor.model = AsyncMock()
    prediction_service.client_manager = AsyncMock()

    # Mock cleanup error
    prediction_service.model.close.side_effect = Exception("Cleanup error")

    with pytest.raises(Exception, match="Cleanup error"):
        await prediction_service.close()

@pytest.mark.asyncio
async def test_service_cleanup_errors():
    """Test service cleanup error cases."""
    # Create fresh service instance for cleanup test
    service = PredictionService(Settings())
    
    # Setup mocks
    mock_model = AsyncMock()
    mock_predictor = AsyncMock()
    mock_client_manager = AsyncMock()
    
    # Configure cleanup error
    mock_model.close.side_effect = Exception("Cleanup error")
    
    # Attach mocks
    service.model = mock_model
    service.predictor = mock_predictor
    service.client_manager = mock_client_manager
    service._initialized = True
    
    # Test cleanup error handling
    with pytest.raises(Exception, match="Cleanup error"):
        await service.close()
    
    # Verify cleanup attempted
    mock_model.close.assert_called_once()

@pytest.mark.asyncio
async def test_initialize_early_return(prediction_service):
    """Test early return when service is already initialized."""
    # Service is already initialized from fixture
    assert prediction_service._initialized
    
    # Mock to verify no further initialization happens
    prediction_service.client_manager = AsyncMock()
    
    await prediction_service.initialize()
    
    # Verify client_manager wasn't touched
    prediction_service.client_manager.assert_not_called()

@pytest.mark.asyncio
async def test_missing_db_handler(test_settings):
    """Test initialization fails when db_handler not set."""
    service = PredictionService(test_settings)
    service.model = AsyncMock()  # Provide model but no db_handler
    
    with pytest.raises(ValidationError, match="Database handler not set"):
        await service.initialize()

@pytest.mark.asyncio
async def test_initialization_error(test_settings):
    """Test service initialization error."""
    service = PredictionService(test_settings)
    
    # 1. First set up DB handler so we get past validation
    service.db_handler = AsyncMock()
    
    # 2. Set up client manager to avoid that initialization
    service.client_manager = AsyncMock()
    service.service_integration = AsyncMock()
    
    # 3. Now set up model to fail
    test_error = Exception("Test error")
    service.model = AsyncMock()
    service.model.initialize.side_effect = test_error
    
    # 4. Error from model.initialize() should propagate
    with pytest.raises(Exception) as exc_info:
        await service.initialize()
    
    assert exc_info.value is test_error
    assert str(exc_info.value) == "Test error"

@pytest.mark.asyncio 
async def test_initialization_error(test_settings):
    """Test model initialization error propagates through service initialization."""
    service = PredictionService(test_settings)
    service.db_handler = AsyncMock()
    
    # Set up model to fail initialization
    mock_model = AsyncMock()
    mock_model.initialize = AsyncMock(side_effect=ModelError("Model initialization failed"))
    
    with patch('app.service.PredictionModel', return_value=mock_model):
        with pytest.raises(ModelError, match="Model initialization failed"):
            await service.initialize()

@pytest.mark.asyncio
async def test_batch_predictions_uninitialized(test_settings, test_prediction_request):
    """Test batch predictions fails when service not initialized."""
    service = PredictionService(test_settings)
    requests = [PredictionRequest(**test_prediction_request)]
    
    with pytest.raises(ValidationError, match="Service not initialized"):
        await service.process_batch_predictions(requests)

@pytest.mark.asyncio
async def test_batch_predictions_success(prediction_service, test_prediction_request):
    """Test successful batch prediction response collection."""
    # Create multiple test requests
    requests = [
        PredictionRequest(**test_prediction_request),
        PredictionRequest(**test_prediction_request)
    ]
    
    # Mock the service integration to avoid external calls
    prediction_service.service_integration.enrich_prediction_request = AsyncMock(
        return_value={
            "intent_patterns": ["pattern1", "pattern2"],
            "user_context": {"location": "US", "device": "mobile"}
        }
    )
    prediction_service.service_integration.analyze_prediction_result = AsyncMock()
    
    # Process batch predictions
    responses = await prediction_service.process_batch_predictions(requests)
    
    # Verify responses were collected and returned
    assert len(responses) == 2
    for response in responses:
        assert response.prediction_id is not None
        assert response.predictions is not None
        assert response.confidence > 0
        assert response.metadata is not None
    
    # Verify service integration was called for each request
    assert prediction_service.service_integration.enrich_prediction_request.call_count == 2
    assert prediction_service.service_integration.analyze_prediction_result.call_count == 2

@pytest.mark.asyncio
async def test_historical_patterns_extraction(prediction_service, test_prediction_request):
    """Test historical patterns extraction from intent service."""
    patterns = ["pattern1", "pattern2"]
    
    # Mock the entire intent_client
    mock_intent_client = AsyncMock()
    mock_intent_client.get_patterns = AsyncMock(return_value={"patterns": patterns})
    prediction_service.client_manager.intent_client = mock_intent_client
    
    analysis = await prediction_service.get_historical_analysis(
        user_id="test_user",
        start_time=datetime(2024, 1, 1),
        end_time=datetime.utcnow()
    )
    
    assert analysis["historical_patterns"] == patterns