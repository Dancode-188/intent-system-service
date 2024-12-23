import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime
from app.ml.service import MLService
from app.models import (
    Pattern,
    PatternType,
    IntentAnalysisRequest,
    IntentAnalysisResponse
)
from app.core.exceptions import MLServiceError

@pytest.mark.unit
class TestMLService:
    @pytest.fixture
    async def service(self):
        """Create a test ML service instance"""
        service = MLService()
        # Mock internal components
        service.bert_handler = AsyncMock()
        service.vector_store = AsyncMock()
        service.pattern_recognizer = AsyncMock()
        await service.initialize()
        return service

    @pytest.fixture
    def sample_pattern(self):
        """Create a test pattern"""
        return Pattern(
            id="test_pattern",
            type=PatternType.SEQUENCE,
            action="view product",
            attributes={"category": "test"}
        )

    @pytest.fixture
    def sample_request(self):
        """Create a test intent analysis request"""
        return IntentAnalysisRequest(
            request_id="test_request",
            action="view product details",
            pattern_type=PatternType.SEQUENCE,
            context={"user_type": "premium"},
            timestamp=datetime.utcnow()
        )

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test ML service initialization"""
        assert service._initialized
        service.pattern_recognizer.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_intent_with_patterns(self, service, sample_request):
        """Test intent analysis with matching patterns"""
        # Mock pattern recognizer response
        service.pattern_recognizer.find_similar_patterns.return_value = [
            {
                "pattern_id": "test_pattern",
                "confidence": 0.85,
                "type": PatternType.SEQUENCE.value,
                "metadata": {
                    "type": PatternType.SEQUENCE.value
                }
            }
        ]

        response = await service.analyze_intent(sample_request)

        assert isinstance(response, IntentAnalysisResponse)
        assert response.request_id == sample_request.request_id
        assert response.primary_intent == PatternType.SEQUENCE.value
        assert response.confidence == 0.85
        assert len(response.patterns) == 1

        service.pattern_recognizer.find_similar_patterns.assert_called_once_with(
            action=sample_request.action,
            pattern_type=sample_request.pattern_type,
            context_filter=sample_request.context
        )

    @pytest.mark.asyncio
    async def test_analyze_intent_no_patterns(self, service, sample_request):
        """Test intent analysis with no matching patterns"""
        service.pattern_recognizer.find_similar_patterns.return_value = []

        response = await service.analyze_intent(sample_request)

        assert isinstance(response, IntentAnalysisResponse)
        assert response.primary_intent is None
        assert response.confidence == 0.0
        assert len(response.patterns) == 0

    @pytest.mark.asyncio
    async def test_store_pattern(self, service, sample_pattern):
        """Test pattern storage"""
        expected_result = {
            "pattern_id": sample_pattern.id,
            "embedding_size": 768,
            "metadata": {"type": sample_pattern.type.value}
        }
        service.pattern_recognizer.store_pattern.return_value = expected_result

        result = await service.store_pattern(sample_pattern)

        assert result == expected_result
        service.pattern_recognizer.store_pattern.assert_called_once_with(
            pattern=sample_pattern,
            context=None
        )

    @pytest.mark.asyncio
    async def test_analyze_sequence(self, service):
        """Test sequence analysis"""
        actions = ["view", "add", "checkout"]
        expected_result = [{
            "start_index": 0,
            "window_size": 3,
            "actions": actions,
            "patterns": [{"action": "view", "patterns": []}]
        }]
        service.pattern_recognizer.analyze_sequence.return_value = expected_result

        result = await service.analyze_sequence(actions)

        assert result == expected_result
        service.pattern_recognizer.analyze_sequence.assert_called_once_with(
            actions=actions,
            window_size=3
        )

    @pytest.mark.asyncio
    async def test_get_pattern(self, service):
        """Test pattern retrieval"""
        pattern_id = "test_pattern"
        expected_result = {
            "pattern_id": pattern_id,
            "type": PatternType.SEQUENCE.value,
            "embedding_size": 768
        }
        service.pattern_recognizer.get_pattern.return_value = expected_result

        result = await service.get_pattern(pattern_id)

        assert result == expected_result
        service.pattern_recognizer.get_pattern.assert_called_once_with(pattern_id)

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, service):
        """Test health check when all components are healthy"""
        service.bert_handler.is_initialized = True
        service.vector_store.is_initialized = True
        service.vector_store.total_vectors = 100

        health = await service.health_check()

        assert health["status"] == "healthy"
        assert health["bert_handler"] == "healthy"
        assert health["vector_store"]["status"] == "healthy"
        assert health["vector_store"]["total_vectors"] == 100

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, service):
        """Test health check when some components are not initialized"""
        service.bert_handler.is_initialized = False
        service.vector_store.is_initialized = True

        health = await service.health_check()

        assert health["status"] == "degraded"
        assert health["bert_handler"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_cleanup(self, service):
        """Test service cleanup"""
        await service.close()

        assert not service._initialized
        service.pattern_recognizer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, service, sample_request):
        """Test error handling in service methods"""
        service.pattern_recognizer.find_similar_patterns.side_effect = Exception("Test error")

        with pytest.raises(MLServiceError):
            await service.analyze_intent(sample_request)
        
    @pytest.mark.asyncio
    async def test_initialization_error(self):
        """Test error handling during initialization"""
        service = MLService()
        # Create a mock for the pattern recognizer
        mock_recognizer = AsyncMock()
        mock_recognizer.initialize.side_effect = Exception("Init failed")
        service.pattern_recognizer = mock_recognizer
        
        with pytest.raises(MLServiceError, match="ML Service initialization failed"):
            await service.initialize()
        assert not service._initialized

    @pytest.mark.asyncio
    async def test_store_pattern_error(self, service, sample_pattern):
        """Test error handling during pattern storage"""
        service.pattern_recognizer.store_pattern.side_effect = Exception("Storage failed")
        
        with pytest.raises(MLServiceError, match="Pattern storage failed"):
            await service.store_pattern(sample_pattern)

    @pytest.mark.asyncio
    async def test_analyze_sequence_error(self, service):
        """Test error handling during sequence analysis"""
        service.pattern_recognizer.analyze_sequence.side_effect = Exception("Analysis failed")
        
        with pytest.raises(MLServiceError, match="Failed to analyze action sequence"):
            await service.analyze_sequence(["action1", "action2"])

    @pytest.mark.asyncio
    async def test_get_pattern_error(self, service):
        """Test error handling during pattern retrieval"""
        service.pattern_recognizer.get_pattern.side_effect = Exception("Retrieval failed")
        
        with pytest.raises(MLServiceError, match="Pattern retrieval failed"):
            await service.get_pattern("test_pattern")

    @pytest.mark.asyncio
    async def test_health_check_error(self, service):
        """Test health check error handling"""
        # Create a mock that raises an exception
        def raise_error(*args, **kwargs):
            raise Exception("Health check error")
            
        # Mock is_initialized to raise exception
        service.bert_handler = MagicMock()
        type(service.bert_handler).is_initialized = PropertyMock(side_effect=raise_error)
        
        health = await service.health_check()
        
        assert health["status"] == "error"
        assert "Health check error" in health["error"]

    @pytest.mark.asyncio
    async def test_cleanup_error(self, service):
        """Test error handling during cleanup"""
        service.pattern_recognizer.close.side_effect = Exception("Cleanup failed")
        
        with pytest.raises(MLServiceError, match="Failed to clean up ML Service"):
            await service.close()

    @pytest.mark.asyncio
    async def test_health_check_component_statuses(self, service):
        """Test different component status combinations"""
        # Test mixed status
        service.bert_handler.is_initialized = True
        service.vector_store.is_initialized = False
        
        health = await service.health_check()
        assert health["status"] == "degraded"
        assert health["bert_handler"] == "healthy"
        assert health["vector_store"] == "not_initialized"
        
        # Test unknown status
        service.bert_handler.is_initialized = None
        health = await service.health_check()
        assert "unknown" in health.values()