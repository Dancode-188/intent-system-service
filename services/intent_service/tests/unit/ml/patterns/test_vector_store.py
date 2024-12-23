import pytest
import numpy as np
import logging
import faiss
from datetime import datetime
from unittest.mock import patch, AsyncMock
from app.ml.patterns.vector_store import VectorStore

@pytest.mark.unit
class TestVectorStore:
    @pytest.fixture
    async def store(self):
        """Create a vector store instance"""
        store = VectorStore(dimension=768)
        await store.initialize()
        yield store
        await store.clear()

    @pytest.fixture
    def sample_vector(self):
        """Create a sample vector"""
        return np.random.randn(768).astype(np.float32)

    @pytest.fixture
    def sample_vectors(self):
        """Create sample vectors"""
        return np.random.randn(5, 768).astype(np.float32)

    @pytest.mark.asyncio
    async def test_initialization(self, store):
        """Test vector store initialization"""
        assert store.is_initialized
        assert store._index is not None
        assert store.dimension == 768
        assert store.total_vectors == 0

    @pytest.mark.asyncio
    async def test_add_vector(self, store, sample_vector):
        """Test adding a single vector"""
        intent_id = "test_intent"
        metadata = {"type": "test"}
        
        await store.add_vector(intent_id, sample_vector, metadata)
        
        assert store.total_vectors == 1
        assert intent_id in store._metadata
        assert store._metadata[intent_id]["type"] == "test"

    @pytest.mark.asyncio
    async def test_add_vectors_batch(self, store, sample_vectors):
        """Test adding multiple vectors"""
        intent_ids = [f"intent_{i}" for i in range(5)]
        metadata = [{"type": "test"} for _ in range(5)]
        
        await store.add_vectors(intent_ids, sample_vectors, metadata)
        
        assert store.total_vectors == 5
        assert all(id in store._metadata for id in intent_ids)

    @pytest.mark.asyncio
    async def test_search(self, store, sample_vector):
        """Test vector similarity search"""
        # Add some test vectors
        intent_id = "test_intent"
        await store.add_vector(intent_id, sample_vector)
        
        # Search with the same vector
        results = await store.search(sample_vector, k=1)
        
        assert len(results) == 1
        assert results[0]["intent_id"] == intent_id
        assert "similarity" in results[0]

    @pytest.mark.asyncio
    async def test_get_vector(self, store, sample_vector):
        """Test retrieving vector by intent ID"""
        intent_id = "test_intent"
        await store.add_vector(intent_id, sample_vector)
        
        vector = await store.get_vector(intent_id)
        
        assert vector is not None
        np.testing.assert_array_almost_equal(vector, sample_vector)

    @pytest.mark.asyncio
    async def test_delete_vector(self, store, sample_vector):
        """Test deleting a vector"""
        intent_id = "test_intent"
        await store.add_vector(intent_id, sample_vector)
        
        assert await store.delete_vector(intent_id)
        assert store.total_vectors == 0
        assert intent_id not in store._metadata

    @pytest.mark.asyncio
    async def test_clear(self, store, sample_vector):
        """Test clearing all vectors"""
        await store.add_vector("test_intent", sample_vector)
        assert store.total_vectors == 1
        
        await store.clear()
        assert store.total_vectors == 0
        assert not store._metadata

    @pytest.mark.asyncio
    async def test_uninitialized_error(self):
        """Test error when using uninitialized store"""
        store = VectorStore()
        with pytest.raises(RuntimeError):
            await store.add_vector("test", np.random.randn(768))

    @pytest.mark.asyncio
    async def test_vector_dimension_mismatch(self, store):
        """Test error when vector dimension doesn't match"""
        # Configure mock to return immediately
        if hasattr(store._index, 'add') and isinstance(store._index.add, AsyncMock):
            store._index.add.side_effect = None  # Prevent delayed execution
        
        wrong_dim_vector = np.random.randn(512)
        with pytest.raises(Exception):
            await store.add_vector("test", wrong_dim_vector)

    @pytest.mark.asyncio
    async def test_metadata_mismatch(self, store, sample_vectors):
        """Test error when metadata length doesn't match vectors"""
        intent_ids = [f"intent_{i}" for i in range(5)]
        metadata = [{"type": "test"}]  # Only one metadata dict
        
        with pytest.raises(ValueError):
            await store.add_vectors(intent_ids, sample_vectors, metadata)

    @pytest.mark.asyncio
    async def test_initialization_exception_handling(self):
        """Test exception handling during initialization"""
        # Test with invalid index type
        store = VectorStore(index_type="invalid")
        with pytest.raises(RuntimeError, match="Vector store initialization failed"):
            await store.initialize()

        # Test FAISS initialization error
        with patch('faiss.IndexFlatL2', side_effect=Exception("FAISS error")):
            store = VectorStore()
            with pytest.raises(RuntimeError, match="Vector store initialization failed"):
                await store.initialize()

    @pytest.mark.asyncio
    async def test_vector_normalization(self, store):
        """Test vector normalization"""
        vector = np.array([1.0, 2.0, 3.0])
        normalized = store._normalize_vector(vector)
        assert np.allclose(np.linalg.norm(normalized), 1.0)

    @pytest.mark.asyncio
    async def test_batch_vector_addition_errors(self, store, sample_vectors):
        """Test error cases in batch vector addition"""
        # Test with mismatched intent IDs and vectors
        intent_ids = ["intent_1"]  # Only one ID for multiple vectors
        with pytest.raises(ValueError, match="Number of intent IDs must match"):
            await store.add_vectors(intent_ids, sample_vectors)

        # Test error during batch addition
        with patch.object(store._index, 'add', side_effect=Exception("FAISS error")):
            with pytest.raises(Exception):
                await store.add_vectors([f"intent_{i}" for i in range(5)], sample_vectors)

    @pytest.mark.asyncio
    async def test_search_error_handling(self, store, sample_vector):
        """Test error handling in vector search"""
        # Test with reshape error
        malformed_vector = np.random.randn(768, 2)  # Wrong shape
        with pytest.raises(Exception):
            await store.search(malformed_vector)

        # Test FAISS search error
        with patch.object(store._index, 'search', side_effect=Exception("FAISS error")):
            with pytest.raises(Exception):
                await store.search(sample_vector)

    @pytest.mark.asyncio
    async def test_get_vector_edge_cases(self, store):
        """Test edge cases in vector retrieval"""
        # Test non-existent intent ID
        result = await store.get_vector("nonexistent")
        assert result is None

        # Test reconstruction error
        await store.add_vector("test", np.random.randn(768))
        with patch.object(store._index, 'reconstruct', side_effect=Exception("FAISS error")):
            with pytest.raises(Exception):
                await store.get_vector("test")

    @pytest.mark.asyncio
    async def test_delete_vector_error_handling(self, store, sample_vector):
        """Test error handling in vector deletion"""
        # Test deletion of non-existent vector
        assert not await store.delete_vector("nonexistent")

        # Test error during deletion
        await store.add_vector("test", sample_vector)
        
        # Force an error during deletion by making metadata access fail
        with patch.dict(store._metadata) as mock_metadata:
            mock_metadata["test"]["vector_id"] = -1  # Invalid vector ID
            with pytest.raises(Exception):
                await store.delete_vector("test")

    @pytest.mark.asyncio
    async def test_clear_error_handling(self, store):
        """Test error handling during clear operation"""
        # Test error during index recreation
        with patch('faiss.IndexFlatL2', side_effect=Exception("FAISS error")):
            with pytest.raises(Exception):
                await store.clear()

    @pytest.mark.asyncio
    async def test_logger_messages(self, caplog):
        """Test logger messages are generated"""
        # Set up logger to capture messages
        caplog.set_level(logging.INFO)
        
        # Initialize store - should log info message
        store = VectorStore()
        await store.initialize()
        
        # Check initialization log
        assert "Initialized FAISS index type" in caplog.text

        # Force search error to test error logging
        with patch.object(store._index, 'search', side_effect=Exception("Search failed")):
            with pytest.raises(Exception):
                await store.search(np.random.randn(768))
        
        # Check error log
        assert "Failed to search vectors" in caplog.text

    @pytest.mark.asyncio
    async def test_total_vectors_property(self, store, sample_vector):
        """Test total_vectors property"""
        # Should be 0 initially
        assert store.total_vectors == 0
        
        # Add some vectors
        await store.add_vector("test1", sample_vector)
        assert store.total_vectors == 1
        
        await store.add_vector("test2", sample_vector)
        assert store.total_vectors == 2
        
        # Clear should reset count
        await store.clear()
        assert store.total_vectors == 0

    @pytest.mark.asyncio
    async def test_ip_index_initialization(self):
        """Test initialization with inner product index type"""
        store = VectorStore(index_type="ip")  # Use IP index type
        await store.initialize()
        assert isinstance(store._index, faiss.IndexFlatIP)  # Line 36

    @pytest.mark.asyncio
    async def test_ip_similarity_search(self, sample_vector):
        """Test search with inner product similarity"""
        store = VectorStore(index_type="ip")
        await store.initialize()
        
        # Add vector to search
        await store.add_vector("test", sample_vector)
        
        # Search with return_scores=True to trigger similarity calculation
        results = await store.search(sample_vector, k=1, return_scores=True)
        assert len(results) == 1
        assert "similarity" in results[0]  # Line 177
        assert isinstance(results[0]["similarity"], float)

    @pytest.mark.asyncio
    async def test_ip_index_recreation(self):
        """Test recreation of IP index during clear"""
        store = VectorStore(index_type="ip")
        await store.initialize()
        
        # Clear to trigger index recreation
        await store.clear()  # Line 236
        assert isinstance(store._index, faiss.IndexFlatIP)