# Intent Service ML Documentation

## ML Architecture

### Components Overview

1. **BERT Handler**
   - Manages BERT model for text embeddings
   - Handles batched inference
   - Provides vector representations

2. **Pattern Recognizer**
   - Identifies intent patterns
   - Manages pattern relationships
   - Handles sequence analysis

3. **Vector Store**
   - FAISS-based vector storage
   - Similarity search
   - Vector indexing

## BERT Handler

### Configuration
```python
class BERTHandler:
    def __init__(
        self,
        model_name: str = "bert-base-uncased",
        max_length: int = 512,
        device: str = "cpu"
    )
```

### Key Features
- Asynchronous initialization
- Batch processing support
- Memory-efficient operation
- Error handling and recovery

### Usage Example
```python
handler = BERTHandler()
await handler.initialize()
embedding = await handler.generate_embedding(text)
```

## Pattern Recognizer

### Configuration
```python
class PatternRecognizer:
    def __init__(
        self,
        bert_handler: BERTHandler,
        vector_store: VectorStore,
        min_confidence: float = 0.7,
        max_patterns: int = 5
    )
```

### Key Features
- Pattern storage and retrieval
- Similarity matching
- Sequence analysis
- Context filtering

### Pattern Analysis
1. **Single Pattern Analysis**
   ```python
   result = await recognizer.find_similar_patterns(
       action="view_product",
       pattern_type=PatternType.SEQUENTIAL
   )
   ```

2. **Sequence Analysis**
   ```python
   sequences = await recognizer.analyze_sequence(
       actions=["view", "compare", "add_to_cart"],
       window_size=3
   )
   ```

## Vector Store

### Configuration
```python
class VectorStore:
    def __init__(
        self,
        dimension: int = 768,
        similarity_threshold: float = 0.7,
        index_type: str = "l2"
    )
```

### Features
- FAISS integration
- Efficient similarity search
- Metadata storage
- Vector operations

### Operations
1. **Adding Vectors**
   ```python
   await store.add_vector(
       intent_id="intent_123",
       vector=embedding,
       metadata={"type": "product_view"}
   )
   ```

2. **Searching**
   ```python
   results = await store.search(
       query_vector=embedding,
       k=5,
       return_scores=True
   )
   ```

## ML Service Integration

### Service Flow
1. **Intent Analysis**
   - Text embedding generation
   - Pattern matching
   - Confidence scoring
   - Result aggregation

2. **Pattern Storage**
   - Vector storage
   - Metadata association
   - Relationship mapping

3. **Pattern Retrieval**
   - Vector similarity search
   - Pattern filtering
   - Result formatting

### Example Flow
```python
class MLService:
    async def analyze_intent(
        self,
        request: IntentAnalysisRequest
    ) -> IntentAnalysisResponse:
        # Generate embeddings
        embedding = await self.bert_handler.generate_embedding(
            request.action
        )
        
        # Find similar patterns
        patterns = await self.pattern_recognizer.find_similar_patterns(
            action=request.action,
            pattern_type=request.pattern_type
        )
        
        # Return analysis results
        return IntentAnalysisResponse(
            patterns=patterns,
            confidence=self._calculate_confidence(patterns)
        )
```

## Performance Considerations

### Optimization Techniques
1. **Batch Processing**
   - Use `generate_embeddings` for multiple texts
   - Batch pattern storage operations
   - Optimize search queries

2. **Memory Management**
   - Clear CUDA cache when needed
   - Implement vector pruning
   - Monitor memory usage

3. **Caching Strategy**
   - Cache frequent embeddings
   - Store common pattern results
   - Implement TTL for cached items

### Monitoring

1. **ML Metrics**
   ```python
   PATTERN_CONFIDENCE = Histogram(
       'intent_service_pattern_confidence',
       'Pattern confidence distribution',
       ['pattern_type']
   )
   ```

2. **Performance Tracking**
   ```python
   QUERY_DURATION = Histogram(
       'intent_service_query_duration_seconds',
       'Duration of pattern queries',
       ['operation_type']
   )
   ```

## Error Handling

### ML Service Errors
```python
class MLServiceError(Exception):
    """Raised when ML Service operations fail"""
    pass

class ModelError(Exception):
    """Raised when ML model operations fail"""
    pass
```

### Recovery Strategies
1. Model Initialization
   - Retry with exponential backoff
   - Fallback to CPU if GPU fails
   - Clear cache and retry

2. Vector Operations
   - Implement backup indices
   - Handle partial results
   - Provide degraded service