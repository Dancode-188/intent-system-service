from typing import Dict, Any, Optional
import logging
from .clients import ServiceClientManager
from .exceptions import ServiceError
from .metrics import (
    track_service_request,
    track_enrichment,
    MetricsManager
)
from ..models import PredictionRequest

logger = logging.getLogger(__name__)

class ServiceIntegration:
    """Handles integration with Context and Intent services"""
    
    def __init__(self, client_manager: ServiceClientManager):
        self.clients = client_manager
        self.metrics = MetricsManager()

    @track_enrichment("context")
    async def _enrich_with_context(
        self,
        context_id: str,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich features with context data"""
        try:
            context_data = await self.clients.context_client.get_context(context_id)
            features["context_embedding"] = context_data.get("embedding")
            features["context_metadata"] = context_data.get("metadata")
            self.metrics.update_service_health("context_service", True)
            return features
        except Exception as e:
            self.metrics.update_service_health("context_service", False)
            raise

    @track_enrichment("intent")
    async def _enrich_with_intent(
        self,
        user_id: str,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich features with intent data"""
        try:
            intent_data = await self.clients.intent_client.get_patterns(user_id)
            features["intent_patterns"] = intent_data.get("patterns", [])
            features["intent_metadata"] = intent_data.get("metadata")
            self.metrics.update_service_health("intent_service", True)
            return features
        except Exception as e:
            self.metrics.update_service_health("intent_service", False)
            raise

    async def enrich_prediction_request(
        self,
        request: PredictionRequest
    ) -> Dict[str, Any]:
        """Enrich prediction request with context and intent data"""
        features = request.features.copy()
        
        try:
            # Get context data if available
            if request.context_id:
                features = await self._enrich_with_context(request.context_id, features)

            # Get intent patterns
            features = await self._enrich_with_intent(request.user_id, features)

            return features

        except ServiceError as e:
            logger.warning(f"Service integration partial failure: {e}")
            # Return original features if enrichment fails
            return features

    @track_service_request("intent_service", "analyze_prediction")
    async def analyze_prediction_result(
        self,
        prediction_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Analyze prediction results with other services"""
        try:
            # Share prediction with Intent service
            await self.clients.intent_client.analyze_intent({
                "prediction_id": prediction_id,
                "predictions": result["predictions"],
                "confidence": result["confidence"]
            })
            
            self.metrics.record_prediction_analysis("intent_service", True)
            logger.info(f"Prediction {prediction_id} shared with Intent service")
            
        except ServiceError as e:
            self.metrics.record_prediction_analysis(
                "intent_service",
                False,
                type(e).__name__
            )
            logger.error(f"Failed to analyze prediction {prediction_id}: {e}")