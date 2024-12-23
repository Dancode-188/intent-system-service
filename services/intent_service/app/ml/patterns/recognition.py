from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime
import logging
from ...models import PatternType, Pattern
from ..bert.model import BERTHandler
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

class PatternRecognizer:
    """
    Recognizes and analyzes patterns in user intents using BERT embeddings
    """
    def __init__(
        self,
        bert_handler: BERTHandler,
        vector_store: VectorStore,
        min_confidence: float = 0.7,
        max_patterns: int = 5
    ):
        self.bert = bert_handler
        self.vector_store = vector_store
        self.min_confidence = min_confidence
        self.max_patterns = max_patterns

    async def initialize(self) -> None:
        """Initialize components if not already initialized"""
        if not self.bert.is_initialized:
            await self.bert.initialize()
        if not self.vector_store.is_initialized:
            await self.vector_store.initialize()

    async def store_pattern(
        self, 
        pattern: Pattern,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a new pattern with its embedding

        Args:
            pattern: Pattern model instance
            context: Optional context information

        Returns:
            Dict containing pattern info and embedding details
        """
        try:
            # Generate embedding for pattern action
            embedding = await self.bert.generate_embedding(pattern.action)
            
            # Prepare metadata
            metadata = {
                "type": pattern.type.value,
                "created_at": datetime.utcnow().isoformat(),
                "context": context or {},
                "attributes": pattern.attributes
            }
            
            # Store in vector database
            await self.vector_store.add_vector(
                intent_id=pattern.id,
                vector=embedding,
                metadata=metadata
            )
            
            logger.info(f"Stored pattern {pattern.id} of type {pattern.type}")
            
            return {
                "pattern_id": pattern.id,
                "embedding_size": len(embedding),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to store pattern: {e}")
            raise

    async def find_similar_patterns(
        self,
        action: str,
        pattern_type: Optional[PatternType] = None,
        context_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find patterns similar to the given action

        Args:
            action: User action to analyze
            pattern_type: Optional filter by pattern type
            context_filter: Optional context-based filtering

        Returns:
            List of similar patterns with confidence scores
        """
        try:
            # Generate embedding for action
            query_embedding = await self.bert.generate_embedding(action)
            
            # Search for similar patterns
            similar_patterns = await self.vector_store.search(
                query_vector=query_embedding,
                k=self.max_patterns,
                return_scores=True
            )
            
            # Filter results
            filtered_patterns = []
            for pattern in similar_patterns:
                # Check confidence threshold
                if pattern["similarity"] < self.min_confidence:
                    continue
                    
                metadata = pattern["metadata"]
                
                # Filter by pattern type if specified
                if pattern_type and metadata["type"] != pattern_type.value:
                    continue
                    
                # Filter by context if specified
                if context_filter:
                    pattern_context = metadata.get("context", {})
                    if not all(
                        pattern_context.get(k) == v 
                        for k, v in context_filter.items()
                    ):
                        continue
                
                filtered_patterns.append({
                    "pattern_id": pattern["intent_id"],
                    "confidence": pattern["similarity"],
                    "type": metadata["type"],
                    "metadata": metadata
                })
            
            return filtered_patterns
            
        except Exception as e:
            logger.error(f"Failed to find similar patterns: {e}")
            raise

    async def analyze_sequence(
        self,
        actions: List[str],
        window_size: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Analyze a sequence of actions for patterns
        
        Args:
            actions: List of sequential user actions
            window_size: Size of sliding window for analysis
        
        Returns:
            List of detected pattern sequences
        """
        try:
            if len(actions) < window_size:
                return []

            # Generate embeddings for all actions
            embeddings = await self.bert.generate_embeddings(actions)
            
            sequences = []
            # Analyze using sliding window
            for i in range(len(actions) - window_size + 1):
                window_actions = actions[i:i + window_size]
                
                # Find similar patterns for each action in window
                window_patterns = []
                for j, action in enumerate(window_actions):
                    similar = await self.find_similar_patterns(action)
                    if similar:
                        window_patterns.append({
                            "position": j,
                            "action": action,
                            "patterns": similar
                        })
                
                if window_patterns:
                    sequences.append({
                        "start_index": i,
                        "window_size": window_size,
                        "actions": window_actions,
                        "patterns": window_patterns
                    })
            
            return sequences
            
        except Exception as e:
            logger.error(f"Failed to analyze sequence: {e}")
            raise

    async def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve detailed pattern information"""
        try:
            # Get vector and metadata
            vector = await self.vector_store.get_vector(pattern_id)
            if vector is None:
                return None
                
            metadata = self.vector_store._metadata.get(pattern_id)
            if metadata is None:
                return None
                
            return {
                "pattern_id": pattern_id,
                "type": metadata["type"],
                "created_at": metadata["created_at"],
                "embedding_size": len(vector),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get pattern: {e}")
            raise

    async def close(self) -> None:
        """Cleanup resources"""
        try:
            await self.bert.close()
            await self.vector_store.clear()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise