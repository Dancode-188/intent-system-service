import pytest
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from app.ml.models import PredictionModel
from app.core.exceptions import ModelError

@pytest.mark.asyncio
async def test_model_initialization(model: PredictionModel):
    """Test successful model initialization."""
    assert model._initialized
    assert model.model is not None
    if model.use_scaler:
        assert model.scaler is not None

@pytest.mark.asyncio
async def test_model_prediction(model: PredictionModel):
    """Test model prediction generation."""
    features = {
        "intent_patterns": ["view_product", "add_to_cart"],
        "user_context": {
            "device": "mobile",
            "location": "US"
        }
    }
    
    result = await model.predict(
        features=features,
        prediction_type="short_term"
    )
    
    assert "predictions" in result
    assert "confidence" in result
    assert "metadata" in result
    assert len(result["predictions"]) > 0
    assert 0 <= result["confidence"] <= 1.0
    assert "prediction_type" in result["metadata"]

@pytest.mark.asyncio
async def test_invalid_features(model: PredictionModel):
    """Test model behavior with invalid features."""
    invalid_features = {
        "invalid_key": "invalid_value"
    }
    
    with pytest.raises(ValueError) as exc_info:
        await model.predict(
            features=invalid_features,
            prediction_type="short_term"
        )
    assert "Missing required features" in str(exc_info.value)

@pytest.mark.asyncio
async def test_confidence_calculation(model: PredictionModel):
    """Test confidence score calculation."""
    # Test with balanced probabilities
    balanced_probs = np.array([0.5, 0.5])
    confidence = model._calculate_confidence(balanced_probs)
    assert 0 <= confidence <= 1.0
    
    # Test with skewed probabilities
    skewed_probs = np.array([0.9, 0.1])
    skewed_confidence = model._calculate_confidence(skewed_probs)
    assert skewed_confidence > confidence  # Should be more confident

@pytest.mark.asyncio
async def test_model_cleanup(test_settings):
    """Test model cleanup."""
    model = PredictionModel(
        model_path=test_settings.MODEL_PATH,
        confidence_threshold=0.7
    )
    await model.initialize()
    await model.close()
    
    assert model.model is None
    assert model.scaler is None
    assert not model._initialized

@pytest.mark.asyncio
async def test_model_cleanup(model: PredictionModel):
    """Test model cleanup."""
    await model.close()
    assert model.model is None
    assert model.scaler is None
    assert not model._initialized

@pytest.mark.asyncio
async def test_model_full_initialization():
    """Test model initialization with actual ML components."""
    # Create test model and scaler
    clf = RandomForestClassifier(n_estimators=10)
    X = np.array([[1, 2], [3, 4]])
    y = np.array([0, 1])
    clf.fit(X, y)
    
    model = PredictionModel(
        model_path="test_path",
        confidence_threshold=0.5,
        use_scaler=True
    )
    
    with patch('joblib.load') as mock_load:
        mock_load.side_effect = [clf, StandardScaler()]
        await model.initialize()
        
    assert model._initialized
    assert model.model is not None
    assert model.scaler is not None
    assert hasattr(model.model, 'predict_proba')

@pytest.mark.asyncio
async def test_feature_encoding():
    """Test feature encoding functionality."""
    model = PredictionModel(
        model_path="test_path",
        confidence_threshold=0.5
    )
    
    features = {
        "intent_patterns": ["pattern1", "pattern2"],
        "user_context": {"location": "US", "device": "mobile"}
    }
    
    encoded = model._preprocess_features(features)  # Changed from _encode_features to _preprocess_features
    assert isinstance(encoded, np.ndarray)
    assert encoded.shape[1] > 0  # Should have at least one feature

@pytest.mark.asyncio
async def test_model_prediction_workflow():
    """Test the complete prediction workflow."""
    model = PredictionModel(
        model_path="test_path",
        confidence_threshold=0.5
    )
    
    # Mock internal components
    mock_clf = MagicMock()
    mock_clf.predict_proba.return_value = np.array([[0.7, 0.3]])
    mock_clf.classes_ = np.array(["action1", "action2"])
    
    model.model = mock_clf
    model._initialized = True
    
    features = {
        "intent_patterns": ["pattern1"],
        "user_context": {"location": "US"}
    }
    
    result = await model.predict(features, "short_term")
    
    assert "predictions" in result
    assert "confidence" in result
    assert "metadata" in result
    assert len(result["predictions"]) > 0
    assert all(isinstance(p["probability"], float) for p in result["predictions"])

@pytest.mark.asyncio
async def test_model_error_handling():
    """Test model error handling scenarios."""
    model = PredictionModel(
        model_path="test_path",
        confidence_threshold=0.5
    )
    
    with pytest.raises(ModelError):
        await model.predict({}, "short_term")  # Empty features
        
    with patch('joblib.load', side_effect=Exception("Test error")):
        with pytest.raises(ModelError):
            await model.initialize()

@pytest.mark.asyncio
async def test_feature_scaling():
    """Test feature scaling transformation."""
    model = PredictionModel(
        model_path="test_path",
        confidence_threshold=0.5,
        use_scaler=True
    )
    
    # Setup mock scaler
    mock_scaler = MagicMock()
    mock_scaler.transform.return_value = np.array([[0.5, -0.5]])
    model.scaler = mock_scaler
    model.use_scaler = True
    
    features = {
        "intent_patterns": ["pattern1"],
        "user_context": {"location": "US"}
    }
    
    result = model._preprocess_features(features)
    assert mock_scaler.transform.called
    assert isinstance(result, np.ndarray)

@pytest.mark.asyncio
async def test_pattern_diversity_edge_case(model: PredictionModel):
    """Test pattern diversity calculation edge case."""
    # Empty patterns should return 0.0
    assert model._calculate_pattern_diversity([]) == 0.0

@pytest.mark.asyncio
async def test_prediction_value_error(model: PredictionModel):
    """Test ValueError handling in predict."""
    features = {
        "intent_patterns": ["pattern1"],
        # Missing user_context
    }
    
    with pytest.raises(ValueError) as exc_info:
        await model.predict(features, "short_term")
    assert "Missing required features" in str(exc_info.value)

@pytest.mark.asyncio
async def test_prediction_general_error(model: PredictionModel):
    """Test general error handling in predict."""
    features = {
        "intent_patterns": ["pattern1"],
        "user_context": {"location": "US"}
    }
    
    # Create mock model with error behavior
    mock_model = MagicMock()
    mock_model.predict_proba = MagicMock(side_effect=Exception("Test error"))
    
    # Override the model's predict method
    old_predict = model.predict
    old_model = model.model
    try:
        model.model = mock_model
        model.predict = PredictionModel.predict.__get__(model, PredictionModel)  # Get original method
        
        with pytest.raises(ModelError) as exc_info:
            await model.predict(features, "short_term")
        assert "Failed to generate prediction: Test error" in str(exc_info.value)
    finally:
        # Restore original predict method and model
        model.predict = old_predict
        model.model = old_model

@pytest.mark.asyncio
async def test_prediction_value_error_handling(model: PredictionModel):
    """Test ValueError handling in predict method."""
    features = {
        "intent_patterns": ["pattern1"],
        "user_context": {"location": "US"}
    }
    
    # Store original predict_proba method
    orig_predict_proba = model.model.predict_proba
    
    try:
        # Mock predict_proba to raise ValueError
        model.model.predict_proba = MagicMock(side_effect=ValueError("Invalid input"))
        # Remove predict mock to use original method
        model.predict = PredictionModel.predict.__get__(model, PredictionModel)
        
        with pytest.raises(ValueError) as exc_info:
            await model.predict(features, "short_term")
        
        assert "Invalid input" in str(exc_info.value)
        
    finally:
        # Restore original methods
        model.model.predict_proba = orig_predict_proba