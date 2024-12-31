import numpy as np
from sklearn.base import BaseEstimator
from sklearn.preprocessing import StandardScaler
import joblib
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from ..core.exceptions import ModelError

logger = logging.getLogger(__name__)

class PredictionModel:
    """
    Manages ML models for prediction generation
    """
    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.7,
        use_scaler: bool = True
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.use_scaler = use_scaler
        self.model: Optional[BaseEstimator] = None
        self.scaler: Optional[StandardScaler] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize model and scaler"""
        try:
            # Load model
            self.model = joblib.load(f"{self.model_path}/prediction_model.joblib")
            
            # Load scaler if needed
            if self.use_scaler:
                self.scaler = joblib.load(f"{self.model_path}/scaler.joblib")
            
            self._initialized = True
            logger.info("Prediction model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            raise ModelError(f"Model initialization failed: {str(e)}")

    def _validate_features(self, features: Dict[str, Any]) -> None:
        """Validate input features"""
        required_features = {"intent_patterns", "user_context"}
        missing = required_features - set(features.keys())
        
        if missing:
            raise ValueError(f"Missing required features: {missing}")

    def _preprocess_features(self, features: Dict[str, Any]) -> np.ndarray:
        """Preprocess features for prediction"""
        # Extract numerical features
        numerical_features = self._extract_numerical_features(features)
        
        # Convert to numpy array
        feature_array = np.array(numerical_features).reshape(1, -1)
        
        # Scale if needed
        if self.use_scaler and self.scaler:
            feature_array = self.scaler.transform(feature_array)
            
        return feature_array

    def _extract_numerical_features(self, features: Dict[str, Any]) -> List[float]:
        """Extract numerical features from input dictionary"""
        numerical_features = []
        
        # Process intent patterns
        intent_patterns = features.get("intent_patterns", [])
        numerical_features.extend([
            len(intent_patterns),  # Number of patterns
            self._calculate_pattern_diversity(intent_patterns)  # Pattern diversity
        ])
        
        # Process user context
        user_context = features.get("user_context", {})
        numerical_features.extend([
            self._encode_context_feature(user_context.get("device", "unknown")),
            self._encode_context_feature(user_context.get("location", "unknown"))
        ])
        
        return numerical_features

    def _calculate_pattern_diversity(self, patterns: List[str]) -> float:
        """Calculate diversity score for intent patterns"""
        if not patterns:
            return 0.0
        unique_patterns = len(set(patterns))
        return unique_patterns / len(patterns)

    def _encode_context_feature(self, feature: str) -> float:
        """Encode categorical context features"""
        # Simple hash-based encoding, can be replaced with more sophisticated encoding
        return float(hash(feature) % 100) / 100.0

    def _calculate_confidence(self, probabilities: np.ndarray) -> float:
        """Calculate confidence score for predictions"""
        # Use max probability as base confidence
        base_confidence = float(np.max(probabilities))
        
        # Adjust based on probability distribution
        entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))
        max_entropy = -np.log2(1.0 / len(probabilities))
        entropy_factor = 1 - (entropy / max_entropy)
        
        # Combine factors
        confidence = (base_confidence + entropy_factor) / 2
        return min(max(confidence, 0.0), 1.0)

    async def predict(
        self,
        features: Dict[str, Any],
        prediction_type: str
    ) -> Dict[str, Any]:
        """
        Generate predictions with confidence scores
        """
        if not self._initialized:
            raise ModelError("Model not initialized")
            
        try:
            # Validate input
            self._validate_features(features)
            
            # Preprocess features
            feature_array = self._preprocess_features(features)
            
            # Generate predictions
            probabilities = self.model.predict_proba(feature_array)[0]
            predicted_classes = self.model.classes_
            
            # Calculate confidence
            confidence = self._calculate_confidence(probabilities)
            
            # Filter predictions by confidence threshold
            predictions = []
            for cls, prob in zip(predicted_classes, probabilities):
                if prob >= self.confidence_threshold:
                    predictions.append({
                        "action": cls,
                        "probability": float(prob)
                    })
            
            # Sort by probability
            predictions.sort(key=lambda x: x["probability"], reverse=True)
            
            return {
                "predictions": predictions,
                "confidence": confidence,
                "metadata": {
                    "model_version": getattr(self.model, "version", "unknown"),
                    "prediction_type": prediction_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "feature_count": len(feature_array[0])
                }
            }
            
        except ValueError as e:
            logger.error(f"Prediction failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise ModelError(f"Failed to generate prediction: {str(e)}")

    async def close(self) -> None:
        """Cleanup resources"""
        self.model = None
        self.scaler = None
        self._initialized = False
        logger.info("Prediction model resources cleaned up")