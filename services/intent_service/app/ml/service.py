from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from .bert.model import BERTHandler
from .patterns.vector_store import VectorStore
from .patterns.recognition import PatternRecognizer
from ..models import Pattern, PatternType, IntentAnalysisRequest, IntentAnalysisResponse
from ..core.exceptions import MLServiceError

logger = logging.getLogger(__name__)

class MLService:
    """
    Coordinates ML operations for intent analysis
    """
    def __init__(self):
        self.bert_handler = BERTHandler()
        self.vector_store = VectorStore()
        self.pattern_recognizer = PatternRecognizer(
            bert_handler=self.bert_handler,
            vector_store=self.vector_store
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all ML components"""
        try:
            if not self._initialized:
                logger.info("Initializing ML Service components...")
                await self.pattern_recognizer.initialize()
                self._initialized = True
                logger.info("ML Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ML Service: {e}")
            raise MLServiceError("ML Service initialization failed") from e

    async def analyze_intent(
        self,
        request: IntentAnalysisRequest
    ) -> IntentAnalysisResponse:
        """
        Analyze user intent from request

        Args:
            request: Intent analysis request containing action and context

        Returns:
            IntentAnalysisResponse with identified patterns and predictions
        """
        try:
            # Find similar patterns
            similar_patterns = await self.pattern_recognizer.find_similar_patterns(
                action=request.action,
                pattern_type=request.pattern_type,
                context_filter=request.context
            )

            # Determine primary intent if patterns found
            primary_intent = None
            confidence = 0.0
            if similar_patterns:
                # Use highest confidence pattern
                top_pattern = max(similar_patterns, key=lambda p: p["confidence"])
                primary_intent = top_pattern["metadata"].get("type")
                confidence = top_pattern["confidence"]

            return IntentAnalysisResponse(
                request_id=request.request_id,
                timestamp=datetime.utcnow(),
                patterns=similar_patterns,
                primary_intent=primary_intent,
                confidence=confidence
            )

        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            raise MLServiceError("Failed to analyze intent") from e

    async def store_pattern(
        self,
        pattern: Pattern,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a new pattern for future matching

        Args:
            pattern: Pattern to store
            context: Optional context information

        Returns:
            Dict containing pattern details and storage confirmation
        """
        try:
            result = await self.pattern_recognizer.store_pattern(
                pattern=pattern,
                context=context
            )
            logger.info(f"Stored pattern {pattern.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to store pattern: {e}")
            raise MLServiceError("Pattern storage failed") from e

    async def analyze_sequence(
        self,
        actions: List[str],
        window_size: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Analyze a sequence of actions for patterns

        Args:
            actions: List of sequential actions
            window_size: Size of sliding window

        Returns:
            List of detected pattern sequences
        """
        try:
            return await self.pattern_recognizer.analyze_sequence(
                actions=actions,
                window_size=window_size
            )

        except Exception as e:
            logger.error(f"Sequence analysis failed: {e}")
            raise MLServiceError("Failed to analyze action sequence") from e

    async def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve pattern details by ID

        Args:
            pattern_id: Unique pattern identifier

        Returns:
            Pattern details if found, None otherwise
        """
        try:
            return await self.pattern_recognizer.get_pattern(pattern_id)

        except Exception as e:
            logger.error(f"Failed to retrieve pattern: {e}")
            raise MLServiceError("Pattern retrieval failed") from e

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of ML components

        Returns:
            Dict containing health status of components
        """
        status = {
            "initialized": self._initialized,
            "bert_handler": "unknown",
            "vector_store": "unknown",
            "pattern_recognizer": "unknown"
        }

        try:
            # Check BERT handler
            if self.bert_handler.is_initialized:
                status["bert_handler"] = "healthy"
            else:
                status["bert_handler"] = "not_initialized"

            # Check vector store
            if self.vector_store.is_initialized:
                total_vectors = self.vector_store.total_vectors
                status["vector_store"] = {
                    "status": "healthy",
                    "total_vectors": total_vectors
                }
            else:
                status["vector_store"] = "not_initialized"

            # Overall status
            status["status"] = "healthy" if all(
                s != "not_initialized" and s != "unknown"
                for s in [status["bert_handler"], status["vector_store"]]
            ) else "degraded"

            return status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def close(self) -> None:
        """Cleanup ML service resources"""
        try:
            await self.pattern_recognizer.close()
            self._initialized = False
            logger.info("ML Service shut down successfully")
        except Exception as e:
            logger.error(f"Error during ML Service cleanup: {e}")
            raise MLServiceError("Failed to clean up ML Service") from e