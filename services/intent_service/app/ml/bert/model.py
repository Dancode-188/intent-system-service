from typing import Optional, List, Dict, Any
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class BERTHandler:
    """
    Handles BERT model operations for generating text embeddings for intent analysis.
    Uses the [CLS] token representation as a sentence-level embedding.
    
    Attributes:
        model_name (str): Name of the BERT model to use
        max_length (int): Maximum sequence length for tokenization
        device (str): Device to run model on ('cpu' or 'cuda')
        _model (Optional[AutoModel]): The BERT model instance
        _tokenizer (Optional[AutoTokenizer]): The BERT tokenizer instance
    """
    def __init__(
        self, 
        model_name: str = "bert-base-uncased",
        max_length: int = 512,
        device: str = "cpu"
    ):
        """
        Initialize the BERT handler.
        
        Args:
            model_name: HuggingFace model identifier
            max_length: Maximum sequence length for tokenization
            device: Device to run model on ('cpu' or 'cuda')
        """
        self.model_name = model_name
        self.max_length = max_length
        self.device = device
        self._model: Optional[AutoModel] = None
        self._tokenizer: Optional[AutoTokenizer] = None
        
    async def initialize(self) -> None:
        """
        Initialize BERT model and tokenizer asynchronously.
        
        Raises:
            RuntimeError: If initialization fails
        """
        try:
            logger.info(f"Initializing BERT model: {self.model_name}")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name)
            self._model.to(self.device)
            self._model.eval()  # Set to evaluation mode
            logger.info("BERT model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BERT model: {e}")
            raise RuntimeError(f"BERT initialization failed: {str(e)}")

    @property
    def is_initialized(self) -> bool:
        """Check if model and tokenizer are initialized."""
        return self._model is not None and self._tokenizer is not None

    def _ensure_initialized(self) -> None:
        """
        Ensure model is initialized before use.
        
        Raises:
            RuntimeError: If model is not initialized
        """
        if not self.is_initialized:
            raise RuntimeError("BERT model not initialized. Call initialize() first.")

    def _mean_pooling(self, token_embeddings: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Perform mean pooling on token embeddings using attention mask.
        
        Args:
            token_embeddings: Token-level embeddings from BERT
            attention_mask: Attention mask for valid tokens
            
        Returns:
            torch.Tensor: Mean-pooled sentence embeddings
        """
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    @torch.no_grad()
    async def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate vector embedding for input text.
        
        Args:
            text: Input text to generate embedding for
            
        Returns:
            np.ndarray: Vector embedding of shape (768,) for base BERT
            
        Raises:
            RuntimeError: If model not initialized
            ValueError: If input text is empty
        """
        self._ensure_initialized()
        
        if not text.strip():
            raise ValueError("Input text cannot be empty")

        try:
            # Tokenize text
            tokens = self._tokenizer(
                text,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt"
            )

            # Move tokens to device
            tokens = {k: v.to(self.device) for k, v in tokens.items()}
            
            # Generate embeddings
            outputs = self._model(**tokens, return_dict=True)
            
            # Get hidden states and mean pool
            token_embeddings = outputs.last_hidden_state
            sentence_embedding = self._mean_pooling(token_embeddings, tokens["attention_mask"])
            
            # Convert to numpy and return
            return sentence_embedding.cpu().detach().numpy().squeeze()

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    @torch.no_grad()
    async def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of input texts
            
        Returns:
            np.ndarray: Matrix of embeddings of shape (n_texts, 768) for base BERT
            
        Raises:
            RuntimeError: If model not initialized
            ValueError: If texts list is empty
        """
        self._ensure_initialized()
        
        if not texts:
            raise ValueError("Input texts list cannot be empty")

        try:
            # Tokenize all texts
            tokens = self._tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt"
            )

            # Move tokens to device
            tokens = {k: v.to(self.device) for k, v in tokens.items()}

            # Generate embeddings
            outputs = self._model(**tokens, return_dict=True)
            
            # Get hidden states and mean pool
            token_embeddings = outputs.last_hidden_state
            sentence_embeddings = self._mean_pooling(token_embeddings, tokens["attention_mask"])
            
            # Convert to numpy and ensure correct shape
            embeddings = sentence_embeddings.cpu().detach().numpy()
            if embeddings.shape[0] != len(texts):
                raise RuntimeError(f"Expected embeddings shape ({len(texts)}, 768), but got {embeddings.shape}")

            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings batch: {e}")
            raise

    async def close(self) -> None:
        """
        Clean up resources.
        
        Raises:
            Exception: If cleanup fails
        """
        try:
            if self._model is not None:
                self._model.cpu()
                self._model = None
            self._tokenizer = None
            torch.cuda.empty_cache()
            logger.info("BERT handler cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up BERT handler: {e}")
            raise Exception("Error cleaning up BERT handler") from e