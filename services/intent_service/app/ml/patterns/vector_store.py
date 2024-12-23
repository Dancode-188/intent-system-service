from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import faiss
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Manages vector embeddings storage and similarity search using FAISS
    """
    def __init__(
        self,
        dimension: int = 768,  # BERT base dimension
        similarity_threshold: float = 0.7,
        index_type: str = "l2"
    ):
        self.dimension = dimension
        self.similarity_threshold = similarity_threshold
        self.index_type = index_type
        self._index: Optional[faiss.Index] = None
        self._id_map: Dict[int, str] = {}  # Maps FAISS ids to intent IDs
        self._metadata: Dict[str, Dict[str, Any]] = {}  # Stores metadata for each vector
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """
        Initialize FAISS index
        """
        try:
            if self.index_type == "l2":
                self._index = faiss.IndexFlatL2(self.dimension)
            elif self.index_type == "ip":  # Inner product
                self._index = faiss.IndexFlatIP(self.dimension)
            else:
                raise ValueError(f"Unsupported index type: {self.index_type}")
            
            logger.info(f"Initialized FAISS index type {self.index_type}")
        except Exception as e:
            logger.error(f"Failed to initialize FAISS index: {e}")
            raise RuntimeError(f"Vector store initialization failed: {str(e)}")

    @property
    def is_initialized(self) -> bool:
        """Check if index is initialized"""
        return self._index is not None

    def _ensure_initialized(self) -> None:
        """Ensure index is initialized before use"""
        if not self.is_initialized:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector for consistent similarity computation"""
        return vector / np.linalg.norm(vector)

    async def add_vector(
        self,
        intent_id: str,
        vector: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a vector to the index
        
        Args:
            intent_id: Unique identifier for the intent
            vector: Vector embedding
            metadata: Optional metadata to store with the vector
        """
        self._ensure_initialized()
        
        async with self._lock:
            try:
                # Ensure vector is the right shape
                vector = vector.reshape(1, -1)
                
                # Add to FAISS index
                vector_id = self._index.ntotal
                self._index.add(vector)
                
                # Update mappings
                self._id_map[vector_id] = intent_id
                self._metadata[intent_id] = {
                    "added_at": datetime.utcnow().isoformat(),
                    "vector_id": vector_id,
                    **(metadata or {})
                }
                
                logger.debug(f"Added vector for intent {intent_id}")
            except Exception as e:
                logger.error(f"Failed to add vector: {e}")
                raise

    async def add_vectors(
        self,
        intent_ids: List[str],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add multiple vectors to the index
        
        Args:
            intent_ids: List of intent IDs
            vectors: Matrix of vectors (n_vectors x dimension)
            metadata: Optional list of metadata dicts
        """
        self._ensure_initialized()
        
        if len(intent_ids) != vectors.shape[0]:
            raise ValueError("Number of intent IDs must match number of vectors")
        
        if metadata and len(metadata) != len(intent_ids):
            raise ValueError("Number of metadata dicts must match number of vectors")
        
        async with self._lock:
            try:
                start_id = self._index.ntotal
                self._index.add(vectors)
                
                # Update mappings
                for i, intent_id in enumerate(intent_ids):
                    vector_id = start_id + i
                    self._id_map[vector_id] = intent_id
                    self._metadata[intent_id] = {
                        "added_at": datetime.utcnow().isoformat(),
                        "vector_id": vector_id,
                        **(metadata[i] if metadata else {})
                    }
                
                logger.debug(f"Added {len(intent_ids)} vectors")
            except Exception as e:
                logger.error(f"Failed to add vectors batch: {e}")
                raise

    async def search(
        self,
        query_vector: np.ndarray,
        k: int = 5,
        return_scores: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors
        
        Args:
            query_vector: Vector to search for
            k: Number of results to return
            return_scores: Whether to include similarity scores
            
        Returns:
            List of dicts containing intent IDs and optionally scores
        """
        self._ensure_initialized()
        
        try:
            # Reshape query vector
            query_vector = query_vector.reshape(1, -1)
            
            # Search index
            distances, indices = self._index.search(query_vector, k)
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx != -1:  # FAISS returns -1 for no match
                    intent_id = self._id_map[idx]
                    result = {
                        "intent_id": intent_id,
                        "metadata": self._metadata[intent_id]
                    }
                    if return_scores:
                        if self.index_type == "l2":
                            similarity = 1 / (1 + dist)  # Convert L2 distance to similarity
                        else:
                            similarity = dist  # IP similarity
                        result["similarity"] = float(similarity)
                    results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            raise

    async def get_vector(self, intent_id: str) -> Optional[np.ndarray]:
        """Retrieve vector by intent ID"""
        self._ensure_initialized()
        
        try:
            metadata = self._metadata.get(intent_id)
            if metadata:
                vector_id = metadata["vector_id"]
                vector = self._index.reconstruct(vector_id)
                return vector
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve vector: {e}")
            raise

    async def delete_vector(self, intent_id: str) -> bool:
        """
        Delete a vector by intent ID
        
        Returns:
            bool: True if vector was deleted, False if not found
        """
        self._ensure_initialized()
        
        async with self._lock:
            try:
                metadata = self._metadata.get(intent_id)
                if metadata:
                    vector_id = metadata["vector_id"]
                    # FAISS doesn't support deletion, so we'll need to rebuild
                    # Remove from mappings
                    del self._id_map[vector_id]
                    del self._metadata[intent_id]
                    logger.info(f"Deleted vector for intent {intent_id}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Failed to delete vector: {e}")
                raise

    async def clear(self) -> None:
        """Clear all vectors and metadata"""
        self._ensure_initialized()
        
        async with self._lock:
            try:
                # Reset FAISS index
                if self.index_type == "l2":
                    self._index = faiss.IndexFlatL2(self.dimension)
                else:
                    self._index = faiss.IndexFlatIP(self.dimension)
                
                # Clear mappings
                self._id_map.clear()
                self._metadata.clear()
                logger.info("Cleared vector store")
            except Exception as e:
                logger.error(f"Failed to clear vector store: {e}")
                raise

    @property
    def total_vectors(self) -> int:
        """Get total number of vectors in the store"""
        return len(self._id_map)