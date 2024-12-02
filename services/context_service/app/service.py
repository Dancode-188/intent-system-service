from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from datetime import datetime
from typing import Dict
from .models import ContextRequest, ContextResponse
from .config import Settings

class ContextService:
    def __init__(self, settings: Settings):
        """
        Initialize the Context Service with necessary models and configurations
        """
        self.settings = settings
        self.tokenizer = AutoTokenizer.from_pretrained(settings.MODEL_NAME)
        self.model = AutoModel.from_pretrained(settings.MODEL_NAME)
        self.max_length = settings.MAX_SEQUENCE_LENGTH

    async def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for input text using BERT
        """
        # Tokenize and prepare input
        inputs = self.tokenizer(
            text,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )

        # Generate embeddings
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use [CLS] token embedding as sequence representation
            embeddings = outputs.last_hidden_state[:, 0, :].numpy()

        return embeddings[0]  # Return the first (and only) embedding

    async def process_context(self, request: ContextRequest) -> ContextResponse:
        """
        Process context request and generate context embedding
        """
        # Combine action and context into text representation
        context_text = f"{request.action} {self._format_context(request.context)}"
        
        # Generate embedding
        embedding = await self.generate_embedding(context_text)
        
        # Calculate confidence based on embedding properties
        confidence = self._calculate_confidence(embedding)
        
        # Determine action type
        action_type = self._classify_action(request.action, embedding)
        
        return ContextResponse(
            context_id=f"ctx_{hash(str(embedding))}",
            embedding=embedding.tolist(),
            confidence=confidence,
            action_type=action_type,
            processed_timestamp=datetime.utcnow()
        )

    def _format_context(self, context: Dict[str, any]) -> str:
        """
        Format context dictionary into text representation
        """
        return " ".join([f"{k}:{v}" for k, v in context.items()])

    def _calculate_confidence(self, embedding: np.ndarray) -> float:
        """
        Calculate confidence score based on embedding properties
        """
        # Simplified confidence calculation based on embedding norm
        norm = np.linalg.norm(embedding)
        return float(min(max(norm / 10.0, 0.0), 1.0))

    def _classify_action(self, action: str, embedding: np.ndarray) -> str:
        """
        Classify action type based on action string and embedding
        """
        action_lower = action.lower()
        if "view" in action_lower or "browse" in action_lower:
            return "exploration"
        elif "search" in action_lower or "find" in action_lower:
            return "search"
        elif "purchase" in action_lower or "buy" in action_lower:
            return "transaction"
        else:
            return "other"