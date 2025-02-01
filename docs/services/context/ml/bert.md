# BERT Implementation Guide

## Overview

This document details the BERT implementation in the Context Service, focusing on the technical aspects of embedding generation and model management.

## Model Architecture

### DistilBERT Configuration

```python
{
    "attention_probs_dropout_prob": 0.1,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "max_position_embeddings": 512,
    "num_attention_heads": 12,
    "num_hidden_layers": 6,
    "pad_token_id": 0,
    "vocab_size": 30522
}
```

## Implementation Details

### 1. Model Handler

```python
class BERTHandler:
    def __init__(self, model_name: str, max_length: int):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.max_length = max_length
        
        # Enable evaluation mode
        self.model.eval()
        
        # Move to GPU if available
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    @torch.no_grad()
    async def generate_embedding(self, text: str) -> np.ndarray:
        # Implementation in section 2
        pass

    async def batch_generate_embeddings(
        self, 
        texts: List[str]
    ) -> List[np.ndarray]:
        # Implementation in section 3
        pass
```

### 2. Single Embedding Generation

```python
@torch.no_grad()
async def generate_embedding(self, text: str) -> np.ndarray:
    # Tokenize input
    encoded = self.tokenizer(
        text,
        max_length=self.max_length,
        padding='max_length',
        truncation=True,
        return_tensors='pt'
    )
    
    # Move to device
    input_ids = encoded['input_ids'].to(self.device)
    attention_mask = encoded['attention_mask'].to(self.device)
    
    # Generate embedding
    outputs = self.model(
        input_ids=input_ids,
        attention_mask=attention_mask
    )
    
    # Extract [CLS] token embedding
    embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    
    return embedding[0]
```

### 3. Batch Processing

```python
async def batch_generate_embeddings(
    self, 
    texts: List[str]
) -> List[np.ndarray]:
    # Tokenize batch
    encoded = self.tokenizer(
        texts,
        max_length=self.max_length,
        padding=True,
        truncation=True,
        return_tensors='pt'
    )
    
    # Process in batches
    batch_size = 32
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch_encoded = {
            'input_ids': encoded['input_ids'][i:i+batch_size].to(self.device),
            'attention_mask': encoded['attention_mask'][i:i+batch_size].to(self.device)
        }
        
        outputs = self.model(**batch_encoded)
        batch_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        embeddings.extend(batch_embeddings)
    
    return embeddings
```

## Privacy-Preserving Features

### 1. Token Filtering

```python
def _filter_sensitive_tokens(self, tokens: List[str]) -> List[str]:
    """Remove potentially sensitive tokens"""
    filtered_tokens = []
    for token in tokens:
        if not self._is_sensitive(token):
            filtered_tokens.append(token)
    return filtered_tokens

def _is_sensitive(self, token: str) -> bool:
    """Check if token contains sensitive information"""
    sensitive_patterns = [
        r'\b[\w\.-]+@[\w\.-]+\.\w+\b',  # email
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # phone
        # Add more patterns as needed
    ]
    return any(re.match(pattern, token) for pattern in sensitive_patterns)
```

### 2. Differential Privacy

```python
def _apply_differential_privacy(
    self, 
    embedding: np.ndarray,
    epsilon: float = 0.1,
    delta: float = 1e-5
) -> np.ndarray:
    """Apply differential privacy to embedding"""
    sensitivity = 1.0
    noise_scale = np.sqrt(2 * np.log(1.25/delta)) / epsilon
    noise = np.random.laplace(0, sensitivity * noise_scale, embedding.shape)
    return embedding + noise
```

## Model Management

### 1. Model Loading

```python
async def load_model(self) -> None:
    """Load model with retries"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            self.model = AutoModel.from_pretrained(self.model_name)
            self.model.eval()
            self.model.to(self.device)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1 * (attempt + 1))
```

### 2. Resource Management

```python
async def cleanup(self) -> None:
    """Release model resources"""
    if hasattr(self, 'model'):
        # Clear CUDA cache if using GPU
        if self.device.type == 'cuda':
            torch.cuda.empty_cache()
        
        # Clear model
        self.model = None
        self.tokenizer = None
```

## Error Handling

```python
class BERTError(Exception):
    """Base exception for BERT-related errors"""
    pass

class ModelLoadError(BERTError):
    """Raised when model loading fails"""
    pass

class EmbeddingError(BERTError):
    """Raised when embedding generation fails"""
    pass
```

## Performance Optimization

### 1. Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def _get_cached_embedding(self, text: str) -> np.ndarray:
    """Cache embeddings for frequently used text"""
    return self.generate_embedding(text)
```

### 2. Batch Size Optimization

```python
def _optimize_batch_size(self) -> int:
    """Dynamically adjust batch size based on available memory"""
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.get_device_properties(0).total_memory
        return min(32, max(1, gpu_mem // (768 * 4 * 1024)))
    return 16  # Default CPU batch size
```

## Testing

```python
@pytest.mark.asyncio
async def test_bert_handler():
    handler = BERTHandler("distilbert-base-uncased", 512)

    # Test single embedding
    text = "test context"
    embedding = await handler.generate_embedding(text)
    assert embedding.shape == (768,)

    # Test batch processing
    texts = ["test1", "test2", "test3"]
    embeddings = await handler.batch_generate_embeddings(texts)
    assert len(embeddings) == len(texts)
    assert all(e.shape == (768,) for e in embeddings)
```