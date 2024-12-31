from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from .models import PredictionRequest, PredictionResponse, PredictionType
from .ml.predictor import Predictor
from .ml.models import PredictionModel
from .db.timescale import TimescaleDBHandler
from .core.exceptions import ModelError, ValidationError, ServiceError
from .core.clients import ServiceClientManager
from .core.integration import ServiceIntegration
from .config import Settings

logger = logging.getLogger(__name__)

class PredictionService:
    """Core Prediction Service implementation"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_handler: Optional[TimescaleDBHandler] = None
        self.model: Optional[PredictionModel] = None
        self.predictor: Optional[Predictor] = None
        self.client_manager: Optional[ServiceClientManager] = None
        self.service_integration: Optional[ServiceIntegration] = None
        self._initialized = False

    def set_db_handler(self, handler: TimescaleDBHandler) -> None:
        """Set the database handler for the service."""
        self.db_handler = handler

    def _validate_request(self, request: PredictionRequest) -> None:
        """Validate prediction request."""
        if not request.user_id:
            raise ValidationError("Missing user_id")
        if not request.context_id:
            raise ValidationError("Missing context_id")
        if not request.features:
            raise ValidationError("Missing features")
        required_features = {"intent_patterns", "user_context"}
        if not all(key in request.features for key in required_features):
            raise ValidationError(f"Missing required features: {required_features}")

    async def initialize(self) -> None:
        """Initialize service components"""
        if self._initialized:
            return

        try:
            # Initialize service clients
            self.client_manager = ServiceClientManager(self.settings)
            self.service_integration = ServiceIntegration(self.client_manager)

            # Initialize ML model if not already set
            if not self.model:
                self.model = PredictionModel(
                    model_path=self.settings.MODEL_PATH,
                    confidence_threshold=self.settings.CONFIDENCE_THRESHOLD
                )
                await self.model.initialize()

            # Initialize predictor
            if self.db_handler:
                self.predictor = Predictor(
                    model=self.model,
                    db_handler=self.db_handler,
                    max_predictions=self.settings.MAX_PREDICTIONS
                )
                self._initialized = True
            else:
                raise ValidationError("Database handler not set")

        except Exception as e:
            logger.error(f"Failed to initialize prediction service: {e}")
            raise

    async def process_prediction(
        self,
        request: PredictionRequest
    ) -> PredictionResponse:
        """Process prediction request with service integration"""
        if not self._initialized:
            raise ValidationError("Service not initialized")

        try:
            # Validate request
            self._validate_request(request)

            # Enrich features with context and intent data
            enriched_features = await self.service_integration.enrich_prediction_request(request)
            
            # Generate prediction
            response = await self.predictor.generate_prediction(
                request.model_copy(update={"features": enriched_features})
            )

            # Analyze prediction results with other services
            await self.service_integration.analyze_prediction_result(
                response.prediction_id,
                {
                    "predictions": response.predictions,
                    "confidence": response.confidence,
                    "metadata": response.metadata
                }
            )

            logger.info(f"Generated prediction {response.prediction_id} "
                       f"with confidence {response.confidence}")

            return response

        except (ModelError, ValidationError, ServiceError) as e:
            logger.error(f"Prediction processing error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in prediction processing: {e}")
            raise ModelError(f"Prediction processing failed: {str(e)}")

    async def process_batch_predictions(
        self,
        requests: List[PredictionRequest]
    ) -> List[PredictionResponse]:
        """Process batch prediction requests"""
        if not self._initialized:
            raise ValidationError("Service not initialized")

        responses = []
        errors = []

        for request in requests:
            try:
                response = await self.process_prediction(request)
                responses.append(response)
            except Exception as e:
                errors.append({
                    "request_id": id(request),
                    "error": str(e)
                })
                logger.error(f"Batch prediction error: {e}")

        if errors and not responses:
            raise ModelError(f"Batch processing failed: {errors}")

        return responses

    async def get_historical_analysis(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Get historical prediction analysis"""
        if not self._initialized:
            raise ValidationError("Service not initialized")

        try:
            # Get historical predictions
            predictions = await self.db_handler.get_historical_predictions(
                user_id, start_time, end_time
            )

            # Get prediction metrics - fix method name
            metrics = await self.db_handler.get_metrics(  # Changed from get_prediction_metrics
                start_time=start_time,
                end_time=end_time
            )

            # Get intent patterns for historical context
            try:
                intent_data = await self.client_manager.intent_client.get_patterns(user_id)
                historical_patterns = intent_data.get("patterns", [])
            except ServiceError:
                historical_patterns = []
                logger.warning(f"Could not fetch historical patterns for user {user_id}")

            analysis = {
                "prediction_count": len(predictions),
                "average_confidence": sum(p["confidence"] for p in predictions) / len(predictions) if predictions else 0,
                "metrics": metrics,
                "predictions": predictions,
                "historical_patterns": historical_patterns
            }

            return analysis

        except Exception as e:
            logger.error(f"Failed to get historical analysis: {e}")
            raise

    async def close(self) -> None:
        """Cleanup service resources"""
        try:
            if self.predictor:
                await self.predictor.model.close()
                self.predictor = None
            if self.model:
                await self.model.close()
                self.model = None
            if self.client_manager:
                await self.client_manager.close()
                self.client_manager = None
            if self.service_integration:
                self.service_integration = None
            self._initialized = False
            logger.info("Service resources cleaned up")
        except Exception as e:
            logger.error(f"Error during service cleanup: {e}")
            raise