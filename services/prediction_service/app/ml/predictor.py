from typing import Dict, Any, Optional
import logging
from datetime import datetime
import uuid
from .models import PredictionModel
from ..models import PredictionRequest, PredictionResponse
from ..db.timescale import TimescaleDBHandler
from ..core.exceptions import ModelError, ValidationError

logger = logging.getLogger(__name__)

class Predictor:
    """
    Coordinates prediction generation and storage
    """
    def __init__(
        self,
        model: PredictionModel,
        db_handler: TimescaleDBHandler,
        max_predictions: int = 10
    ):
        self.model = model
        self.db = db_handler
        self.max_predictions = max_predictions

    async def generate_prediction(
        self,
        request: PredictionRequest
    ) -> PredictionResponse:
        """
        Generate and store predictions from request
        """
        try:
            # Generate prediction ID
            prediction_id = f"pred_{uuid.uuid4().hex[:8]}"
            
            # Get model predictions
            result = await self.model.predict(
                features=request.features,
                prediction_type=request.prediction_type
            )
            
            # Limit number of predictions
            result["predictions"] = result["predictions"][:self.max_predictions]
            
            # Store prediction
            await self.db.store_prediction(
                prediction_id=prediction_id,
                user_id=request.user_id,
                context_id=request.context_id,
                prediction_type=request.prediction_type.value,
                predictions=result["predictions"],
                confidence=result["confidence"],
                metadata=result["metadata"]
            )
            
            # Store metrics
            await self._store_metrics(prediction_id, result)
            
            return PredictionResponse(
                prediction_id=prediction_id,
                predictions=result["predictions"],
                confidence=result["confidence"],
                metadata=result["metadata"],
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to generate prediction: {e}")
            if isinstance(e, (ModelError, ValidationError)):
                raise
            raise ModelError(f"Prediction generation failed: {str(e)}")

    async def _store_metrics(
        self,
        prediction_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Store prediction metrics"""
        try:
            metrics = {
                "confidence": result["confidence"],
                "prediction_count": len(result["predictions"]),
                "top_probability": result["predictions"][0]["probability"]
                if result["predictions"] else 0.0
            }
            
            for metric_name, metric_value in metrics.items():
                await self.db.store_metric(
                    prediction_id=prediction_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    tags={"prediction_type": result["metadata"]["prediction_type"]}
                )
                
        except Exception as e:
            logger.warning(f"Failed to store metrics: {e}")
            # Don't fail the whole prediction for metrics storage failure

    async def get_prediction(
        self,
        prediction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a stored prediction"""
        return await self.db.get_prediction(prediction_id)