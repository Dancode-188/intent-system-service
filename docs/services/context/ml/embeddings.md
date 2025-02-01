# Context Embeddings Guide

## Overview

This document details the embedding generation, analysis, and utilization processes in the Context Service. The service uses 768-dimensional BERT embeddings to represent user context and actions.

## Embedding Generation

### 1. Text Preprocessing

```python
def preprocess_text(text: str) -> str:
    """Prepare text for embedding generation"""
    # Normalize whitespace
    text = " ".join(text.split())
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    
    return text
```

### 2. Context Formatting

```python
def format_context(context: Dict[str, Any]) -> str:
    """Format context dictionary into text representation"""
    context_pairs = []
    for key, value in context.items():
        # Handle different value types
        if isinstance(value, (int, float)):
            context_pairs.append(f"{key}:{value}")
        elif isinstance(value, bool):
            context_pairs.append(f"{key}:{'yes' if value else 'no'}")
        else:
            context_pairs.append(f"{key}:{str(value)}")
    
    return " ".join(context_pairs)
```

### 3. Embedding Generation Pipeline

```python
async def generate_context_embedding(
    action: str,
    context: Dict[str, Any]
) -> np.ndarray:
    """Generate embedding for action and context"""
    # Format input text
    action_text = preprocess_text(action)
    context_text = format_context(context)
    combined_text = f"{action_text} {context_text}"
    
    # Generate embedding
    embedding = await bert_handler.generate_embedding(combined_text)
    
    # Apply privacy preservation
    embedding = apply_privacy_measures(embedding)
    
    return embedding
```

## Vector Operations

### 1. Vector Normalization

```python
def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """L2 normalize embedding vector"""
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm
```

### 2. Similarity Calculations

```python
def calculate_similarity(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
    metric: str = 'cosine'
) -> float:
    """Calculate similarity between embeddings"""
    if metric == 'cosine':
        return np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        )
    elif metric == 'euclidean':
        return 1 / (1 + np.linalg.norm(embedding1 - embedding2))
    else:
        raise ValueError(f"Unsupported similarity metric: {metric}")
```

### 3. Dimensionality Reduction

```python
def reduce_dimensions(
    embedding: np.ndarray,
    target_dim: int = 64
) -> np.ndarray:
    """Reduce embedding dimensions for visualization/storage"""
    from sklearn.decomposition import PCA
    
    pca = PCA(n_components=target_dim)
    reduced = pca.fit_transform(embedding.reshape(1, -1))
    return reduced[0]
```

## Privacy Preservation

### 1. Differential Privacy

```python
def apply_differential_privacy(
    embedding: np.ndarray,
    epsilon: float = 0.1,
    delta: float = 1e-5
) -> np.ndarray:
    """Apply differential privacy to embedding"""
    # Calculate sensitivity
    sensitivity = 1.0
    
    # Calculate noise scale
    noise_scale = np.sqrt(2 * np.log(1.25/delta)) / epsilon
    
    # Generate and add noise
    noise = np.random.laplace(0, sensitivity * noise_scale, embedding.shape)
    private_embedding = embedding + noise
    
    # Normalize to maintain vector properties
    return normalize_embedding(private_embedding)
```

### 2. Privacy-Preserving Similarity

```python
def private_similarity_check(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
    threshold: float = 0.8,
    epsilon: float = 0.1
) -> bool:
    """Privacy-preserving similarity comparison"""
    # Add noise to similarity computation
    base_similarity = calculate_similarity(embedding1, embedding2)
    noise = np.random.laplace(0, 1/epsilon)
    noisy_similarity = base_similarity + noise
    
    return noisy_similarity >= threshold
```

## Confidence Scoring

### 1. Basic Confidence

```python
def calculate_confidence(embedding: np.ndarray) -> float:
    """Calculate confidence score for embedding"""
    # Norm-based confidence
    norm = np.linalg.norm(embedding)
    base_confidence = min(norm / 10.0, 1.0)
    
    # Entropy-based adjustment
    entropy = calculate_entropy(embedding)
    entropy_factor = 1 - (entropy / np.log(len(embedding)))
    
    return float(base_confidence * entropy_factor)
```

### 2. Advanced Confidence Metrics

```python
def calculate_embedding_quality(
    embedding: np.ndarray,
    reference_embeddings: List[np.ndarray]
) -> Dict[str, float]:
    """Calculate various quality metrics for embedding"""
    return {
        'base_confidence': calculate_confidence(embedding),
        'coherence': calculate_coherence(embedding),
        'stability': calculate_stability(embedding, reference_embeddings),
        'distinctiveness': calculate_distinctiveness(embedding, reference_embeddings)
    }
```

## Performance Optimization

### 1. Caching Strategy

```python
class EmbeddingCache:
    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.max_size = max_size
        self._lock = asyncio.Lock()
    
    async def get_embedding(
        self,
        key: str,
        generator: Callable
    ) -> np.ndarray:
        """Get or generate embedding with cache"""
        async with self._lock:
            if key in self.cache:
                return self.cache[key]
            
            embedding = await generator()
            
            # Implement LRU if cache is full
            if len(self.cache) >= self.max_size:
                self.cache.pop(next(iter(self.cache)))
            
            self.cache[key] = embedding
            return embedding
```

### 2. Batch Processing

```python
async def batch_process_embeddings(
    contexts: List[Dict],
    batch_size: int = 32
) -> List[np.ndarray]:
    """Process embeddings in batches"""
    results = []
    
    for i in range(0, len(contexts), batch_size):
        batch = contexts[i:i + batch_size]
        batch_results = await asyncio.gather(*(
            generate_context_embedding(**ctx)
            for ctx in batch
        ))
        results.extend(batch_results)
    
    return results
```

## Monitoring & Metrics

### 1. Embedding Quality Metrics

```python
def monitor_embedding_quality(embedding: np.ndarray) -> Dict[str, float]:
    """Calculate quality metrics for monitoring"""
    return {
        'norm': float(np.linalg.norm(embedding)),
        'mean': float(np.mean(embedding)),
        'std': float(np.std(embedding)),
        'min': float(np.min(embedding)),
        'max': float(np.max(embedding)),
        'zeros_ratio': float(np.count_nonzero(embedding == 0) / len(embedding))
    }
```

### 2. Performance Monitoring

```python
async def track_embedding_performance(
    func: Callable
) -> Dict[str, float]:
    """Track embedding generation performance"""
    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss
    
    result = await func()
    
    end_time = time.time()
    end_memory = psutil.Process().memory_info().rss
    
    return {
        'processing_time': end_time - start_time,
        'memory_delta': end_memory - start_memory,
        'embedding_size': result.nbytes
    }
```

## Best Practices

1. **Input Preparation**
   - Always preprocess text inputs
   - Handle missing context values
   - Validate input lengths

2. **Privacy**
   - Apply differential privacy consistently
   - Monitor privacy budgets
   - Regular privacy audits

3. **Performance**
   - Use batching for multiple embeddings
   - Implement caching for frequent contexts
   - Monitor resource usage

4. **Monitoring**
   - Track embedding quality metrics
   - Monitor privacy parameters
   - Log performance statistics