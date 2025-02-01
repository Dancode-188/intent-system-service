# Context Service Performance Tuning Guide

## Overview

This guide provides comprehensive performance optimization strategies for the Context Service, covering model optimization, resource management, caching, and scaling guidelines.

## Model Optimization

### 1. BERT Model Tuning

```python
# ml/optimizations.py
from transformers import AutoModel
import torch

class OptimizedBERTModel:
    def __init__(self, model_name: str):
        self.model = AutoModel.from_pretrained(
            model_name,
            # Use half precision
            torch_dtype=torch.float16,
            # Optimize memory usage
            low_cpu_mem_usage=True,
            # Enable model optimizations
            use_cache=True,
            # Use TorchScript
            torchscript=True
        )
        
        # Move to GPU if available
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        
        # Convert to TorchScript for better performance
        self.model = torch.jit.script(self.model)

    @torch.no_grad()
    async def generate_embedding(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Optimized embedding generation"""
        return self.model(
            input_ids.to(self.device),
            output_hidden_states=True
        ).last_hidden_state[:, 0, :]
```

### 2. Batch Processing

```python
# ml/batch_processor.py
class BatchProcessor:
    def __init__(
        self,
        model: OptimizedBERTModel,
        batch_size: int = 32,
        max_wait_time: float = 0.1
    ):
        self.model = model
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.queue = asyncio.Queue()
        self.processing = False
    
    async def process_items(self):
        """Process items in batches"""
        while True:
            batch = []
            start_time = time.time()
            
            # Collect batch
            while len(batch) < self.batch_size:
                try:
                    # Wait for next item with timeout
                    item = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=self.max_wait_time
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
                
                # Check if we've waited too long
                if time.time() - start_time > self.max_wait_time:
                    break
            
            if batch:
                # Process batch
                embeddings = await self.model.generate_embedding(
                    torch.cat([item['input_ids'] for item in batch])
                )
                
                # Distribute results
                for i, item in enumerate(batch):
                    item['future'].set_result(embeddings[i])
```

## Resource Management

### 1. Memory Optimization

```python
# utils/memory.py
import psutil
import gc

class MemoryManager:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.process = psutil.Process()
    
    def check_memory(self) -> bool:
        """Check memory usage and cleanup if needed"""
        memory_percent = self.process.memory_percent()
        
        if memory_percent > self.threshold:
            self.cleanup()
            return True
        return False
    
    def cleanup(self):
        """Perform memory cleanup"""
        # Clear PyTorch cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Force garbage collection
        gc.collect()
        
        # Clear embedding cache
        self.clear_embedding_cache()
    
    @staticmethod
    def clear_embedding_cache():
        """Clear embedding cache"""
        EmbeddingCache.clear()
```

### 2. CPU Optimization

```python
# utils/cpu.py
class CPUOptimizer:
    @staticmethod
    def set_thread_count(thread_count: Optional[int] = None):
        """Set optimal thread count"""
        if thread_count is None:
            # Use 75% of available cores
            thread_count = max(1, (os.cpu_count() or 1) * 3 // 4)
        
        torch.set_num_threads(thread_count)
        torch.set_num_interop_threads(thread_count)
```

## Caching Strategy

### 1. Multi-level Cache

```python
# cache/multi_level.py
from typing import Optional, Any
import redis

class MultiLevelCache:
    def __init__(
        self,
        redis_client: redis.Redis,
        local_cache_size: int = 1000,
        ttl: int = 3600
    ):
        self.redis = redis_client
        self.local_cache = LRUCache(local_cache_size)
        self.ttl = ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        # Check local cache first
        value = self.local_cache.get(key)
        if value is not None:
            return value
        
        # Check Redis
        value = await self.redis.get(key)
        if value is not None:
            # Update local cache
            self.local_cache.put(key, value)
            return value
        
        return None
    
    async def put(self, key: str, value: Any):
        """Put item in cache"""
        # Update local cache
        self.local_cache.put(key, value)
        
        # Update Redis with TTL
        await self.redis.setex(key, self.ttl, value)
```

### 2. Embedding Cache

```python
# cache/embeddings.py
import numpy as np

class EmbeddingCache:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "embedding:"
    
    async def get_embedding(
        self,
        text: str
    ) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        key = f"{self.prefix}{hash(text)}"
        data = await self.redis.get(key)
        
        if data:
            return np.frombuffer(data, dtype=np.float32)
        return None
    
    async def store_embedding(
        self,
        text: str,
        embedding: np.ndarray,
        ttl: int = 3600
    ):
        """Store embedding in cache"""
        key = f"{self.prefix}{hash(text)}"
        data = embedding.astype(np.float32).tobytes()
        await self.redis.setex(key, ttl, data)
```

## Request Processing Optimization

### 1. Request Pipeline

```python
# service/pipeline.py
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ProcessingStage:
    name: str
    processor: Callable
    batch_size: Optional[int] = None
    timeout: Optional[float] = None

class RequestPipeline:
    def __init__(self, stages: List[ProcessingStage]):
        self.stages = stages
        self.queues = {
            stage.name: asyncio.Queue()
            for stage in stages
        }
    
    async def process_request(
        self,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process request through pipeline"""
        result = request
        
        for stage in self.stages:
            # Add to stage queue
            await self.queues[stage.name].put(result)
            
            # Process through stage
            if stage.batch_size:
                result = await self.process_batch(stage)
            else:
                result = await stage.processor(result)
        
        return result
```

### 2. Connection Pooling

```python
# service/connections.py
class ConnectionPool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis_pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            max_connections=settings.REDIS_POOL_SIZE
        )
    
    def get_redis_connection(self) -> redis.Redis:
        """Get Redis connection from pool"""
        return redis.Redis(connection_pool=self.redis_pool)
```

## Performance Monitoring

### 1. Metrics Collection

```python
# monitoring/metrics.py
from prometheus_client import Histogram, Counter, Gauge

# Processing time metrics
PROCESSING_TIME = Histogram(
    'context_service_processing_seconds',
    'Request processing time in seconds',
    ['stage'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Resource metrics
MEMORY_USAGE = Gauge(
    'context_service_memory_bytes',
    'Memory usage in bytes',
    ['type']
)

GPU_MEMORY = Gauge(
    'context_service_gpu_memory_bytes',
    'GPU memory usage in bytes'
)

# Batch processing metrics
BATCH_SIZE = Histogram(
    'context_service_batch_size',
    'Batch processing size',
    buckets=[1, 5, 10, 20, 32, 50]
)
```

### 2. Performance Alerts

```python
# monitoring/alerts.py
from prometheus_client import Counter

# Performance alerts
PERFORMANCE_ALERTS = Counter(
    'context_service_performance_alerts',
    'Performance-related alerts',
    ['type', 'severity']
)

class PerformanceMonitor:
    def __init__(self, settings: Settings):
        self.settings = settings
    
    async def check_performance(self):
        """Monitor performance metrics"""
        while True:
            try:
                # Check processing time
                p95_latency = PROCESSING_TIME.observe().quantile(0.95)
                if p95_latency > self.settings.MAX_LATENCY:
                    PERFORMANCE_ALERTS.labels(
                        type='high_latency',
                        severity='warning'
                    ).inc()
                
                # Check memory usage
                if MEMORY_USAGE.value > self.settings.MAX_MEMORY:
                    PERFORMANCE_ALERTS.labels(
                        type='high_memory',
                        severity='warning'
                    ).inc()
                
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Performance check failed: {e}")
```

## Scaling Guidelines

### 1. Horizontal Scaling

```python
# scaling/horizontal.py
class ScalingManager:
    def __init__(self, settings: Settings):
        self.settings = settings
    
    async def check_scaling_needs(self):
        """Check if scaling is needed"""
        # Check CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > self.settings.CPU_SCALE_THRESHOLD:
            return "scale_out"
        
        # Check memory usage
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > self.settings.MEMORY_SCALE_THRESHOLD:
            return "scale_out"
        
        # Check request queue
        queue_size = await self.get_queue_size()
        if queue_size > self.settings.QUEUE_SCALE_THRESHOLD:
            return "scale_out"
        
        return None
```

### 2. Load Balancing

```python
# scaling/load_balancer.py
class LoadBalancer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.instances = []
    
    async def route_request(
        self,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route request to least loaded instance"""
        if not self.instances:
            raise RuntimeError("No available instances")
        
        # Get instance loads
        loads = await asyncio.gather(*[
            self.get_instance_load(instance)
            for instance in self.instances
        ])
        
        # Select least loaded instance
        instance = self.instances[loads.index(min(loads))]
        return await instance.process_request(request)
```

## Best Practices

1. **Resource Management**
   - Monitor memory usage
   - Implement cleanup routines
   - Use connection pooling
   - Optimize thread usage

2. **Caching Strategy**
   - Use multi-level caching
   - Implement proper TTL
   - Monitor cache hit rates
   - Regular cache cleanup

3. **Batch Processing**
   - Optimize batch sizes
   - Implement timeouts
   - Monitor batch metrics
   - Handle partial batches

4. **Scaling**
   - Monitor scaling metrics
   - Implement auto-scaling
   - Use load balancing
   - Handle failover