import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import torch
from app.ml.bert.model import BERTHandler

@pytest.mark.unit
class TestBERTHandler:
    @pytest.fixture
    def mock_tokenizer(self):
        tokenizer = MagicMock()
        # Return shape (1, 10) if a single string, else (len(texts), 10).
        def mock_call(text_or_texts, *args, **kwargs):
            if isinstance(text_or_texts, str):
                batch_size = 1
            else:
                batch_size = len(text_or_texts)
            return {
                'input_ids': torch.zeros((batch_size, 10), dtype=torch.long),
                'attention_mask': torch.ones((batch_size, 10), dtype=torch.long)
            }
        tokenizer.side_effect = mock_call
        return tokenizer

    @pytest.fixture
    def mock_model(self):
        model = MagicMock()
        # Return last_hidden_state of shape (batch_size, seq_len, hidden_dim = 768).
        def mock_forward(input_ids, attention_mask, return_dict=True, **kwargs):
            batch_size = input_ids.shape[0]
            seq_len = input_ids.shape[1]
            last_hidden_state = torch.randn(batch_size, seq_len, 768)
            output = MagicMock()
            output.last_hidden_state = last_hidden_state
            return output
        model.side_effect = mock_forward
        model.to = MagicMock(return_value=model)
        model.cpu = MagicMock(return_value=model)
        return model

    @pytest.fixture
    async def handler(self, mock_tokenizer, mock_model):
        """Create a BERT handler instance with mocked components"""
        with patch('app.ml.bert.model.AutoTokenizer') as mock_auto_tokenizer, \
            patch('app.ml.bert.model.AutoModel') as mock_auto_model:
            
            # Configure mocks
            mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
            mock_auto_model.from_pretrained.return_value = mock_model
            
            handler = BERTHandler()
            await handler.initialize()
            yield handler
            try:
                await handler.close()
            except Exception:
                # Ignore cleanup errors in fixture teardown
                pass

    @pytest.mark.asyncio
    async def test_initialization(self, handler):
        """Test BERT handler initialization"""
        assert handler.is_initialized
        assert handler._model is not None
        assert handler._tokenizer is not None

    @pytest.mark.asyncio
    async def test_embedding_generation(self, handler):
        """Test generating embeddings for single text"""
        text = "test example text"
        embedding = await handler.generate_embedding(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (768,)  # BERT base hidden size
        assert not np.isnan(embedding).any()

    @pytest.mark.asyncio
    async def test_batch_embedding_generation(self, handler):
        """Test generating embeddings for multiple texts"""
        texts = ["first text", "second text", "third text"]
        embeddings = await handler.generate_embeddings(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 768)  # (n_texts, hidden_size)
        assert not np.isnan(embeddings).any()

    @pytest.mark.asyncio
    async def test_empty_input_handling(self, handler):
        """Test handling of empty input"""
        with pytest.raises(ValueError):
            await handler.generate_embedding("")
        
        with pytest.raises(ValueError):
            await handler.generate_embeddings([])
            
        with pytest.raises(ValueError):
            await handler.generate_embedding("   ")  # Only whitespace

    @pytest.mark.asyncio
    async def test_uninitialized_error(self):
        """Test error when using uninitialized handler"""
        handler = BERTHandler()
        with pytest.raises(RuntimeError):
            await handler.generate_embedding("test")
            
        with pytest.raises(RuntimeError):
            await handler.generate_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_cleanup(self, handler):
        """Test cleanup of resources"""
        await handler.close()
        assert not handler.is_initialized
        assert handler._model is None
        assert handler._tokenizer is None

    @pytest.mark.asyncio
    async def test_initialization_error(self, mock_tokenizer):
        """Test handling of initialization errors"""
        with patch('app.ml.bert.model.AutoTokenizer') as mock_auto_tokenizer:
            mock_auto_tokenizer.from_pretrained.side_effect = Exception("Test error")
            
            handler = BERTHandler()
            with pytest.raises(RuntimeError) as exc_info:
                await handler.initialize()
            assert "BERT initialization failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embedding_error(self, handler):
        """Test handling of embedding generation errors"""
        handler._model.side_effect = Exception("Test error")
        
        with pytest.raises(Exception) as exc_info:
            await handler.generate_embedding("test text")

    @pytest.mark.asyncio
    async def test_embedding_shape_error(self, handler):
        """Test handling of incorrect embedding shape"""
        def mock_forward_wrong_shape(**kwargs):
            output = MagicMock()
            # Important: Match attention mask batch size to tokens
            batch_size = kwargs['attention_mask'].shape[0]
            output.last_hidden_state = torch.randn(1, 10, 768)  # Intentionally wrong batch size
            return output
                
        handler._model.side_effect = mock_forward_wrong_shape
        
        with pytest.raises(RuntimeError, match="must match the existing size"):
            await handler.generate_embeddings(["first", "second"])

    @pytest.mark.asyncio
    async def test_mean_pooling_calculation(self, handler):
        """Test mean pooling with masked values"""
        # Create test data with specific masked values
        token_embeddings = torch.tensor([
            [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],  # First sequence
            [[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]  # Second sequence
        ], dtype=torch.float32)
        
        attention_mask = torch.tensor([
            [1, 1, 0],  # First sequence: mask last token
            [1, 1, 1]   # Second sequence: use all tokens
        ])
        
        result = handler._mean_pooling(token_embeddings, attention_mask)
        
        # First sequence should average only first two tokens
        expected_first = torch.tensor([2.0, 3.0])  # Average of [1,2] and [3,4]
        # Second sequence should average all tokens
        expected_second = torch.tensor([9.0, 10.0])  # Average of [7,8], [9,10], and [11,12]
        
        assert torch.allclose(result[0], expected_first, atol=1e-6)
        assert torch.allclose(result[1], expected_second, atol=1e-6)

    @pytest.mark.asyncio
    async def test_device_handling(self):
        """Test handling of different devices"""
        # Test CPU device
        cpu_handler = BERTHandler(device="cpu")
        await cpu_handler.initialize()
        cpu_result = await cpu_handler.generate_embedding("test")
        assert isinstance(cpu_result, np.ndarray)
        await cpu_handler.close()
        
        # Test CUDA device if available
        if torch.cuda.is_available():
            with patch('torch.cuda.empty_cache') as mock_empty_cache:
                cuda_handler = BERTHandler(device="cuda")
                await cuda_handler.initialize()
                cuda_result = await cuda_handler.generate_embedding("test")
                assert isinstance(cuda_result, np.ndarray)
                await cuda_handler.close()
                mock_empty_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self, handler):
        """Test error handling during cleanup"""
        # Create a new mock to avoid affecting other tests
        error_model = MagicMock()
        error_model.cpu.side_effect = RuntimeError("GPU error")
        handler._model = error_model
        
        with pytest.raises(Exception, match="Error cleaning up BERT handler"):
            await handler.close()

    @pytest.mark.asyncio
    async def test_max_length_handling(self, handler):
        """Test handling of maximum sequence length"""
        long_text = " ".join(["word"] * 1000)  # Create text longer than max_length
        embedding = await handler.generate_embedding(long_text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (768,)
        
        # Test batch with long texts
        long_texts = [long_text] * 3
        embeddings = await handler.generate_embeddings(long_texts)
        assert embeddings.shape == (3, 768)

    @pytest.mark.asyncio
    async def test_tokenization_error(self, handler):
        """Test handling of tokenization errors"""
        # Make the tokenizer raise an exception
        handler._tokenizer.side_effect = Exception("Tokenization failed")
        
        with pytest.raises(Exception) as exc_info:
            await handler.generate_embedding("test text")
        # Verify the error is propagated correctly    
        assert "Tokenization failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_batch_size_validation(self, handler):
        """Test batch size validation"""
        texts = ["text1", "text2"]
        embeddings = await handler.generate_embeddings(texts)
        assert embeddings.shape == (2, 768)

    @pytest.mark.asyncio
    async def test_embedding_shape_mismatch(self, handler):
        """Test handling of incorrect embedding shape output"""
        input_texts = ["first text", "second text"]
        
        # Create a custom mean_pooling function that returns wrong shape
        def mock_mean_pooling(*args, **kwargs):
            # Return 3 embeddings for 2 input texts
            return torch.randn(3, 768)  # Wrong batch size
            
        # Replace the mean_pooling method
        handler._mean_pooling = mock_mean_pooling
        
        # Should raise RuntimeError with our line 179 message
        with pytest.raises(RuntimeError, match=rf"Expected embeddings shape \({len(input_texts)}, 768\)"):
            await handler.generate_embeddings(input_texts)