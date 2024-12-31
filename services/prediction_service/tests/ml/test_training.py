import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from app.ml.training import ModelTrainer

@pytest.fixture
def trainer():
    """Create a model trainer instance."""
    return ModelTrainer(
        model_path="test_models",
        model_config={
            'n_estimators': 10,
            'max_depth': 5,
            'random_state': 42
        }
    )

@pytest.fixture
def sample_data():
    """Create sample training data."""
    return [
        {
            "features": {
                "intent_patterns": ["pattern1", "pattern2"],
                "user_context": {"device": "mobile", "location": "US"}
            },
            "label": 1
        },
        {
            "features": {
                "intent_patterns": ["pattern3"],
                "user_context": {"device": "desktop", "location": "UK"}
            },
            "label": 0
        }
    ]

@pytest.mark.asyncio
async def test_prepare_training_data(trainer, sample_data):
    """Test training data preparation."""
    X, y = trainer.prepare_training_data(sample_data)
    assert isinstance(X, np.ndarray)
    assert isinstance(y, np.ndarray)
    assert len(X) == len(y) == 2
    assert X.shape[1] == 4  # Number of features

@pytest.mark.asyncio
async def test_train_model(trainer, sample_data):
    """Test model training."""
    await trainer.train_model(sample_data)
    assert trainer.model is not None
    assert trainer.scaler is not None
    assert isinstance(trainer.model, RandomForestClassifier)
    assert isinstance(trainer.scaler, StandardScaler)

@pytest.mark.asyncio
async def test_save_model(trainer, sample_data, tmp_path):
    """Test model saving."""
    trainer.model_path = tmp_path
    await trainer.train_model(sample_data)
    await trainer.save_model()
    assert (tmp_path / "prediction_model.joblib").exists()
    assert (tmp_path / "scaler.joblib").exists()

@pytest.mark.asyncio
async def test_evaluate_model(trainer, sample_data):
    """Test model evaluation."""
    await trainer.train_model(sample_data)
    metrics = await trainer.evaluate_model(sample_data)
    assert "accuracy" in metrics
    assert "feature_importance" in metrics
    assert 0 <= metrics["accuracy"] <= 1

@pytest.mark.asyncio
async def test_feature_extraction(trainer):
    """Test numerical feature extraction."""
    features = {
        "intent_patterns": ["pattern1", "pattern2"],
        "user_context": {"device": "mobile", "location": "US"}
    }
    numerical = trainer._extract_numerical_features(features)
    assert len(numerical) == 4
    assert all(isinstance(x, float) for x in numerical)

@pytest.mark.asyncio
async def test_pattern_diversity(trainer):
    """Test pattern diversity calculation."""
    patterns = ["p1", "p2", "p1", "p3"]
    diversity = trainer._calculate_pattern_diversity(patterns)
    assert 0 <= diversity <= 1
    assert diversity == 0.75  # 3 unique / 4 total

@pytest.mark.asyncio
async def test_pattern_diversity_errors(trainer):
    """Test pattern diversity calculation with edge cases."""
    # Test empty patterns
    assert trainer._calculate_pattern_diversity([]) == 0.0
    # Test None patterns
    assert trainer._calculate_pattern_diversity(None) == 0.0
    # Test invalid patterns
    assert trainer._calculate_pattern_diversity([None, None]) == 0.0

@pytest.mark.asyncio
async def test_context_encoding(trainer):
    """Test context feature encoding."""
    # Test with multiple different values
    values = ["mobile", "desktop", "tablet", "laptop"]
    encodings = [trainer._encode_context_feature(v) for v in values]
    
    # Verify all values are unique
    assert len(set(encodings)) == len(values)
    # Verify range
    assert all(0 <= x <= 1 for x in encodings)
    # Verify unknown case
    assert trainer._encode_context_feature("unknown") == 0.0

@pytest.mark.asyncio
async def test_error_handling(trainer):
    with pytest.raises(ValueError):
        await trainer.evaluate_model([])  # Empty data
    
    with pytest.raises(Exception):
        await trainer.save_model()  # No model trained yet

@pytest.mark.asyncio
async def test_symlink_update(trainer, tmp_path):
    """Test model file updates."""
    trainer.model_path = tmp_path
    source = tmp_path / "test_model.joblib"
    source.write_text("test content")  # Add content to source
    trainer._update_symlinks(source, "latest_model")
    target = tmp_path / "latest_model"
    assert target.exists()
    assert target.read_text() == "test content"  # Verify content copied

@pytest.mark.asyncio
async def test_model_training_failure(trainer, sample_data):
    """Test model training error handling."""
    with patch('sklearn.ensemble.RandomForestClassifier.fit', 
              side_effect=Exception("Training failed")):
        with pytest.raises(Exception) as exc_info:
            await trainer.train_model(sample_data)
        assert "Training failed" in str(exc_info.value)

@pytest.mark.asyncio
async def test_model_save_failure(trainer, sample_data, tmp_path):
    """Test model save error handling."""
    # Setup
    trainer.model_path = tmp_path
    await trainer.train_model(sample_data)
    
    with patch('joblib.dump', side_effect=Exception("Save failed")):
        with pytest.raises(Exception) as exc_info:
            await trainer.save_model()
        assert "Save failed" in str(exc_info.value)

@pytest.mark.asyncio
async def test_model_evaluation_failure(trainer, sample_data):
    """Test model evaluation error handling."""
    await trainer.train_model(sample_data)
    
    # Mock model to raise exception during prediction
    trainer.model.predict = MagicMock(side_effect=Exception("Evaluation failed"))
    
    with pytest.raises(Exception) as exc_info:
        await trainer.evaluate_model(sample_data)
    assert "Evaluation failed" in str(exc_info.value)