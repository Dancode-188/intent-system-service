from typing import Optional, Dict, Any, List
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    Handles model training and persistence
    """
    def __init__(
        self,
        model_path: str,
        model_config: Optional[Dict[str, Any]] = None
    ):
        self.model_path = Path(model_path)
        self.model_config = model_config or {
            'n_estimators': 100,
            'max_depth': 10,
            'random_state': 42
        }
        self.model: Optional[BaseEstimator] = None
        self.scaler: Optional[StandardScaler] = None

    def prepare_training_data(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Prepare raw data for training
        """
        features = []
        labels = []
        
        for data in raw_data:
            # Extract features
            numerical_features = self._extract_numerical_features(data['features'])
            features.append(numerical_features)
            labels.append(data['label'])
            
        return np.array(features), np.array(labels)

    def _extract_numerical_features(
        self,
        features: Dict[str, Any]
    ) -> List[float]:
        """
        Extract numerical features from raw input
        """
        numerical_features = []
        
        # Process intent patterns
        intent_patterns = features.get('intent_patterns', [])
        numerical_features.extend([
            float(len(intent_patterns)),  # Explicit float conversion
            float(self._calculate_pattern_diversity(intent_patterns))
        ])
        
        # Process user context
        user_context = features.get('user_context', {})
        numerical_features.extend([
            self._encode_context_feature(user_context.get('device', 'unknown')),
            self._encode_context_feature(user_context.get('location', 'unknown'))
        ])
        
        return numerical_features

    def _calculate_pattern_diversity(self, patterns: List[str]) -> float:
        """Calculate diversity score for patterns"""
        if not patterns or not isinstance(patterns, list):
            return 0.0
            
        # Filter out None and invalid patterns
        valid_patterns = [p for p in patterns if p and isinstance(p, str)]
        if not valid_patterns:
            return 0.0
            
        unique_patterns = len(set(valid_patterns))
        return unique_patterns / len(valid_patterns)

    def _encode_context_feature(self, feature: str) -> float:
        """Encode categorical features with improved hashing"""
        if feature == "unknown":
            return 0.0
        # Use a better hash function that provides more unique values
        import hashlib
        hash_value = int(hashlib.md5(feature.encode()).hexdigest(), 16)
        return (hash_value % 100) / 100.0

    async def train_model(
        self,
        training_data: List[Dict[str, Any]]
    ) -> None:
        """
        Train the prediction model
        """
        try:
            # Prepare data
            X, y = self.prepare_training_data(training_data)
            
            # Initialize and fit scaler
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Initialize and train model
            self.model = RandomForestClassifier(**self.model_config)
            self.model.fit(X_scaled, y)
            
            # Save model and scaler
            await self.save_model()
            
            logger.info("Model training completed successfully")
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise

    async def save_model(self) -> None:
        """
        Save trained model and scaler
        """
        if not self.model:
            raise ValueError("Cannot save: model not trained")
            
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Create model directory if it doesn't exist
            self.model_path.mkdir(parents=True, exist_ok=True)
            
            # Save model
            model_file = self.model_path / f"prediction_model_{timestamp}.joblib"
            joblib.dump(self.model, model_file)
            
            # Save scaler
            if self.scaler:
                scaler_file = self.model_path / f"scaler_{timestamp}.joblib"
                joblib.dump(self.scaler, scaler_file)
            
            # Update latest files with copy instead of symlinks
            self._update_symlinks(model_file, "prediction_model.joblib")
            if self.scaler:
                self._update_symlinks(scaler_file, "scaler.joblib")
                
            logger.info("Model and scaler saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise

    # Update _update_symlinks method to use copy instead of symlinks
    def _update_symlinks(self, source: Path, link_name: str) -> None:
        """Update latest model files with copy instead of symlinks for Windows compatibility"""
        link_path = self.model_path / link_name
        if link_path.exists():
            link_path.unlink()
        # Use copy instead of symlink
        import shutil
        shutil.copy2(source, link_path)

    async def evaluate_model(
        self,
        test_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Evaluate model performance
        """
        if not self.model:
            raise ValueError("Model not trained")
            
        try:
            # Prepare test data
            X_test, y_test = self.prepare_training_data(test_data)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Get predictions
            y_pred = self.model.predict(X_test_scaled)
            y_prob = self.model.predict_proba(X_test_scaled)
            
            # Calculate metrics
            accuracy = (y_test == y_pred).mean()
            
            return {
                "accuracy": float(accuracy),
                "feature_importance": dict(zip(
                    [f"feature_{i}" for i in range(X_test.shape[1])],
                    self.model.feature_importances_.tolist()
                ))
            }
            
        except Exception as e:
            logger.error(f"Model evaluation failed: {e}")
            raise