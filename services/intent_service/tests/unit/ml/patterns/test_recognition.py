import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec
import numpy as np
from datetime import datetime
from app.ml.patterns.recognition import PatternRecognizer
from app.ml.bert.model import BERTHandler
from app.ml.patterns.vector_store import VectorStore
from app.models import Pattern, PatternType

@pytest.mark.unit
class TestPatternRecognizer:
    @pytest.fixture
    def mock_bert_handler(self):
        handler = AsyncMock(spec=BERTHandler)
        handler.is_initialized = True
        
        # Create test vectors
        test_vector = np.random.randn(768)
        test_batch_vectors = np.array([test_vector] * 3)
        
        # Create coroutine return values
        async def async_generate_embedding(*args, **kwargs):
            return test_vector
        
        async def async_generate_embeddings(*args, **kwargs):
            return test_batch_vectors
        
        # Set the mock returns to these coroutines
        handler.generate_embedding.side_effect = async_generate_embedding
        handler.generate_embeddings.side_effect = async_generate_embeddings
        
        return handler

    @pytest.fixture
    def mock_vector_store(self):
        store = AsyncMock(spec=VectorStore)
        store.is_initialized = True
        store._metadata = {}
        # Make the mock's search method return a coroutine
        async def async_search(*args, **kwargs):
            return [{
                "intent_id": "test_pattern",
                "similarity": 0.9,
                "metadata": {
                    "type": PatternType.SEQUENCE.value,
                    "context": {},
                    "created_at": datetime.utcnow().isoformat()
                }
            }]
        store.search.side_effect = async_search
        
        # Make the add_vector method return a coroutine
        async def async_add_vector(*args, **kwargs):
            return True
        store.add_vector.side_effect = async_add_vector
        
        return store

    @pytest.fixture
    async def recognizer(self, mock_bert_handler, mock_vector_store):
        recognizer = PatternRecognizer(mock_bert_handler, mock_vector_store)
        await recognizer.initialize()
        return recognizer

    @pytest.fixture
    def sample_pattern(self):
        return Pattern(
            id="test_pattern",
            type=PatternType.SEQUENCE,
            action="view product details",
            attributes={"category": "product_view"}
        )

    @pytest.mark.asyncio
    async def test_initialization(self, recognizer):
        """Test recognizer initialization"""
        assert recognizer.bert.is_initialized
        assert recognizer.vector_store.is_initialized

    @pytest.mark.asyncio
    async def test_store_pattern(self, recognizer, sample_pattern):
        """Test storing a new pattern"""
        result = await recognizer.store_pattern(sample_pattern)
        
        assert result["pattern_id"] == sample_pattern.id
        assert result["embedding_size"] == 768  # BERT base size
        assert result["metadata"]["type"] == sample_pattern.type.value
        assert "created_at" in result["metadata"]
        assert result["metadata"]["attributes"] == sample_pattern.attributes

    @pytest.mark.asyncio
    async def test_find_similar_patterns(self, recognizer, mock_vector_store):
        """Test finding similar patterns"""
        # Search return value is set in mock_vector_store fixture
        results = await recognizer.find_similar_patterns("test action")
        
        assert len(results) == 1
        assert results[0]["pattern_id"] == "test_pattern"
        assert results[0]["confidence"] >= 0.7
        assert results[0]["type"] == PatternType.SEQUENCE.value

    @pytest.mark.asyncio
    async def test_pattern_type_filtering(self, recognizer, mock_vector_store):
        """Test filtering patterns by type"""
        async def async_search(*args, **kwargs):
            return [
                {
                    "intent_id": "pattern1",
                    "similarity": 0.9,
                    "metadata": {"type": PatternType.SEQUENCE.value}
                },
                {
                    "intent_id": "pattern2",
                    "similarity": 0.8,
                    "metadata": {"type": PatternType.TEMPORAL.value}
                }
            ]
        mock_vector_store.search.side_effect = async_search
        
        results = await recognizer.find_similar_patterns(
            "test action",
            pattern_type=PatternType.SEQUENCE
        )
        
        assert len(results) == 1
        assert results[0]["pattern_id"] == "pattern1"
        assert results[0]["type"] == PatternType.SEQUENCE.value

    @pytest.mark.asyncio
    async def test_analyze_sequence(self, recognizer):
        """Test analyzing action sequences"""
        actions = ["view product", "add to cart", "checkout"]
        
        # Create pre-defined response for find_similar_patterns
        mock_patterns = [{
            "intent_id": f"pattern_{i}",
            "similarity": 0.9,
            "metadata": {"type": PatternType.SEQUENCE.value}
        } for i in range(3)]

        # Mock the find_similar_patterns method properly
        async def mock_find_similar_patterns(*args, **kwargs):
            return [{
                "pattern_id": p["intent_id"],
                "confidence": p["similarity"],
                "type": p["metadata"]["type"],
                "metadata": p["metadata"]
            } for p in mock_patterns]

        recognizer.find_similar_patterns = mock_find_similar_patterns
        
        results = await recognizer.analyze_sequence(actions)
        
        assert len(results) == 1  # One window for 3 actions
        assert results[0]["window_size"] == 3
        assert results[0]["start_index"] == 0
        assert results[0]["actions"] == actions

    @pytest.mark.asyncio
    async def test_get_pattern(self, recognizer, mock_vector_store):
        """Test retrieving pattern details"""
        pattern_id = "test_pattern"
        test_vector = np.random.randn(768)
        
        async def async_get_vector(*args, **kwargs):
            return test_vector
        mock_vector_store.get_vector.side_effect = async_get_vector
        
        mock_vector_store._metadata = {
            pattern_id: {
                "type": PatternType.SEQUENCE.value,
                "created_at": datetime.utcnow().isoformat(),
                "attributes": {"category": "test"}
            }
        }
        
        result = await recognizer.get_pattern(pattern_id)
        
        assert result is not None
        assert result["pattern_id"] == pattern_id
        assert result["type"] == PatternType.SEQUENCE.value
        assert result["embedding_size"] == 768
        assert "created_at" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_confidence_filtering(self, recognizer, mock_vector_store):
        """Test filtering by confidence threshold"""
        async def async_search(*args, **kwargs):
            return [
                {
                    "intent_id": "pattern1",
                    "similarity": 0.9,
                    "metadata": {"type": PatternType.SEQUENCE.value}
                },
                {
                    "intent_id": "pattern2",
                    "similarity": 0.6,  # Below threshold (0.7)
                    "metadata": {"type": PatternType.SEQUENCE.value}
                }
            ]
        mock_vector_store.search.side_effect = async_search
        
        results = await recognizer.find_similar_patterns("test action")
        
        assert len(results) == 1
        assert results[0]["pattern_id"] == "pattern1"

    @pytest.mark.asyncio
    async def test_context_filtering(self, recognizer, mock_vector_store):
        """Test filtering by context"""
        async def async_search(*args, **kwargs):
            return [
                {
                    "intent_id": "pattern1",
                    "similarity": 0.9,
                    "metadata": {
                        "type": PatternType.SEQUENCE.value,
                        "context": {"user_type": "premium"}
                    }
                },
                {
                    "intent_id": "pattern2",
                    "similarity": 0.8,
                    "metadata": {
                        "type": PatternType.SEQUENCE.value,
                        "context": {"user_type": "basic"}
                    }
                }
            ]
        mock_vector_store.search.side_effect = async_search
        
        results = await recognizer.find_similar_patterns(
            "test action",
            context_filter={"user_type": "premium"}
        )
        
        assert len(results) == 1
        assert results[0]["pattern_id"] == "pattern1"

    @pytest.mark.asyncio
    async def test_initialization_error(self, mock_bert_handler, mock_vector_store):
        """Test error handling during initialization"""
        # Make BERT initialization fail
        mock_bert_handler.is_initialized = False
        mock_bert_handler.initialize.side_effect = Exception("BERT init failed")
        
        recognizer = PatternRecognizer(mock_bert_handler, mock_vector_store)
        with pytest.raises(Exception):
            await recognizer.initialize()

    @pytest.mark.asyncio
    async def test_store_pattern_error(self, recognizer, sample_pattern):
        """Test error handling in store_pattern"""
        # Make embedding generation fail
        async def generate_embedding_error(*args, **kwargs):
            raise Exception("Embedding failed")
        recognizer.bert.generate_embedding = generate_embedding_error

        # The actual error will contain the original error message
        with pytest.raises(Exception) as exc_info:
            await recognizer.store_pattern(sample_pattern)
        assert "Embedding failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_find_similar_patterns_error(self, recognizer):
        """Test error handling in find_similar_patterns"""
        # Make vector store search fail
        recognizer.vector_store.search.side_effect = Exception("Search failed")
        
        with pytest.raises(Exception):
            await recognizer.find_similar_patterns("test action")

    @pytest.mark.asyncio
    async def test_analyze_sequence_error(self, recognizer):
        """Test error handling in analyze_sequence"""
        # Test with too short sequence
        result = await recognizer.analyze_sequence(["action1", "action2"])
        assert result == []

        # Test embedding generation error
        async def generate_embeddings_error(*args, **kwargs):
            raise Exception("Embedding failed")
        recognizer.bert.generate_embeddings = generate_embeddings_error

        # The actual error will contain the original error message
        with pytest.raises(Exception) as exc_info:
            await recognizer.analyze_sequence(["action1", "action2", "action3"])
        assert "Embedding failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_pattern_error(self, recognizer):
        """Test error handling in get_pattern"""
        # Test non-existent pattern
        result = await recognizer.get_pattern("non_existent")
        assert result is None
        
        # Test vector store error
        recognizer.vector_store.get_vector.side_effect = Exception("Vector fetch failed")
        with pytest.raises(Exception):
            await recognizer.get_pattern("test_pattern")

    @pytest.mark.asyncio
    async def test_cleanup_error(self, recognizer):
        """Test error handling during cleanup"""
        # Make cleanup fail
        recognizer.bert.close.side_effect = Exception("Cleanup failed")
        
        with pytest.raises(Exception):
            await recognizer.close()

    @pytest.mark.asyncio
    async def test_vector_store_initialization_error(self, mock_bert_handler, mock_vector_store):
        """Test vector store initialization error (line 32)"""
        # Make vector store initialization fail
        mock_vector_store.is_initialized = False
        mock_vector_store.initialize.side_effect = Exception("Vector store init failed")
        
        recognizer = PatternRecognizer(mock_bert_handler, mock_vector_store)
        with pytest.raises(Exception):
            await recognizer.initialize()

    @pytest.mark.asyncio
    async def test_empty_sequence_analysis_edge_case(self, recognizer):
        """Test empty sequence and short sequence edge cases"""
        # Test completely empty sequence
        result1 = await recognizer.analyze_sequence([])
        assert result1 == []
        
        # Force method to execute line 201 with single action
        result2 = await recognizer.analyze_sequence(["single_action"])
        assert result2 == []

    @pytest.mark.asyncio
    async def test_get_pattern_metadata_missing(self, recognizer):
        """Test pattern metadata missing edge case"""
        pattern_id = "test_pattern"
        
        # Set up vector store to return vector but have missing metadata
        test_vector = np.random.randn(768)
        async def get_vector(*args, **kwargs):
            return test_vector
        recognizer.vector_store.get_vector.side_effect = get_vector
        
        # Ensure metadata is missing
        recognizer.vector_store._metadata = {}
        
        # This should hit line 223
        result = await recognizer.get_pattern(pattern_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pattern_vector_none(self, recognizer):
        """Test get_pattern when vector is None but metadata exists"""
        pattern_id = "test_pattern"
        
        # Make get_vector return None
        async def get_vector_none(*args, **kwargs):
            return None
        recognizer.vector_store.get_vector.side_effect = get_vector_none
        
        # Add metadata to make sure we hit the vector None check first
        recognizer.vector_store._metadata = {
            pattern_id: {
                "type": "test",
                "created_at": "2024-01-01"
            }
        }
        
        # This should hit line 201 when vector is None
        result = await recognizer.get_pattern(pattern_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_calls_clear(self, recognizer):
        """Test that cleanup properly calls vector store clear (line 223)"""
        # Track if clear was called
        clear_called = False
        
        async def mock_clear():
            nonlocal clear_called
            clear_called = True
        
        # Replace clear method with our tracking version
        recognizer.vector_store.clear = mock_clear
        
        # Call cleanup
        await recognizer.close()
        
        # Verify clear was called
        assert clear_called, "Vector store clear was not called during cleanup"