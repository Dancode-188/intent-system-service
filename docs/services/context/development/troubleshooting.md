# Context Service Troubleshooting Guide

## Common Issues

### 1. Service Startup Issues

#### BERT Model Loading Failures
```
ERROR: Failed to load BERT model: No such file or directory
```

**Possible Causes:**
- No internet connection during first model download
- Insufficient disk space
- Corrupted model cache

**Solutions:**
```python
# Clear model cache
import shutil
import os

cache_dir = os.path.expanduser('~/.cache/huggingface')
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

# Force model re-download
from transformers import AutoModel, AutoTokenizer
model_name = "distilbert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name, force_download=True)
model = AutoModel.from_pretrained(model_name, force_download=True)
```

#### Memory Issues on Startup
```
ERROR: Unable to allocate memory for BERT model
```

**Solutions:**
```python
# Reduce model memory usage
class ContextService:
    def __init__(self, settings: Settings):
        self.model = AutoModel.from_pretrained(
            settings.MODEL_NAME,
            torch_dtype=torch.float16,  # Use half precision
            low_cpu_mem_usage=True
        )
```

### 2. Runtime Issues

#### High Latency

**Symptoms:**
- Response times > 200ms
- Increasing request queue
- High CPU usage

**Diagnosis:**
```python
# Add performance logging
@contextlib.contextmanager
def time_operation(operation_name: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"{operation_name} took {duration:.3f} seconds")

async def process_context(self, request: ContextRequest):
    with time_operation("embedding_generation"):
        embedding = await self.generate_embedding(text)
```

**Solutions:**
1. Enable batch processing
```python
class BatchProcessor:
    def __init__(self, max_batch_size: int = 32):
        self.queue = asyncio.Queue()
        self.max_batch_size = max_batch_size
        self.processing = False

    async def process_batch(self):
        while True:
            batch = []
            try:
                # Collect batch
                while len(batch) < self.max_batch_size:
                    item = await self.queue.get()
                    batch.append(item)
            except asyncio.TimeoutError:
                pass

            if batch:
                # Process batch
                await self._process_items(batch)

    async def add_item(self, item):
        await self.queue.put(item)
```

2. Optimize model settings
```python
# config.py
class Settings(BaseSettings):
    MAX_SEQUENCE_LENGTH: int = 128  # Reduced from 512
    BATCH_SIZE: int = 32
    USE_FP16: bool = True
```

#### Memory Leaks

**Symptoms:**
- Increasing memory usage over time
- Service crashes after running for extended periods

**Diagnosis:**
```python
# Add memory monitoring
import psutil
import gc

def log_memory_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    logger.info(
        "Memory usage",
        extra={
            "rss": memory_info.rss,
            "vms": memory_info.vms,
            "percent": process.memory_percent()
        }
    )

# Monitor garbage collection
gc.set_debug(gc.DEBUG_STATS)
```

**Solutions:**
1. Implement periodic cleanup
```python
class ContextService:
    async def cleanup(self):
        """Periodic cleanup task"""
        while True:
            try:
                # Clear torch cache
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                # Force garbage collection
                gc.collect()

                # Log memory usage
                log_memory_usage()

                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
```

2. Proper resource management
```python
class EmbeddingGenerator:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Clean up resources
        self.clear_cache()
        
    def clear_cache(self):
        if hasattr(self, '_cache'):
            self._cache.clear()
```

### 3. API Issues

#### Rate Limiting Problems

**Symptoms:**
- Unexpected 429 responses
- Inconsistent rate limit counting

**Diagnosis:**
```python
# Add rate limit debugging
class RateLimiter:
    async def check_rate_limit(self, client_id: str) -> bool:
        try:
            result = await self._check_limit(client_id)
            logger.debug(
                "Rate limit check",
                extra={
                    "client_id": client_id,
                    "allowed": result,
                    "current_count": await self._get_current_count(client_id)
                }
            )
            return result
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow on error
```

**Solutions:**
1. Implement rate limit monitoring
```python
from prometheus_client import Counter, Gauge

RATE_LIMIT_EXCEEDED = Counter(
    'context_service_rate_limit_exceeded_total',
    'Total number of rate limit exceedances',
    ['client_id']
)

RATE_LIMIT_CURRENT = Gauge(
    'context_service_rate_limit_current',
    'Current rate limit count',
    ['client_id']
)
```

2. Add rate limit headers
```python
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add rate limit headers
    client_id = request.state.client_id
    limit = await rate_limiter.get_limit(client_id)
    remaining = await rate_limiter.get_remaining(client_id)
    reset = await rate_limiter.get_reset_time(client_id)
    
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)
    
    return response
```

### 4. Integration Issues

#### Redis Connection Problems

**Symptoms:**
- Rate limiting failures
- Cache misses
- Increased latency

**Diagnosis:**
```python
# Add Redis health checking
async def check_redis_health() -> dict:
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        
        # Get Redis info
        info = await redis_client.info()
        return {
            "status": "healthy",
            "connected_clients": info["connected_clients"],
            "used_memory": info["used_memory_human"],
            "operations_per_second": info["instantaneous_ops_per_sec"]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

**Solutions:**
1. Implement connection pooling
```python
class RedisManager:
    def __init__(self, settings: Settings):
        self.pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            max_connections=settings.REDIS_POOL_SIZE,
            socket_timeout=settings.REDIS_TIMEOUT
        )
    
    def get_client(self) -> redis.Redis:
        return redis.Redis(connection_pool=self.pool)
```

2. Add retry logic
```python
from tenacity import retry, stop_after_attempt, wait_exponential

class RedisClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def execute_with_retry(self, func, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis operation failed: {e}, retrying...")
            raise
```

## Debugging Procedures

### 1. Enable Debug Logging

```python
# logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'handlers': {
        'debug_file': {
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'detailed',
            'level': 'DEBUG'
        }
    },
    'formatters': {
        'detailed': {
            'format': '%(asctime)s %(name)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
        }
    }
}
```

### 2. Performance Profiling

```python
# profiling.py
import cProfile
import pstats
import io

def profile_function(func):
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats()
        logger.debug(f"Profile for {func.__name__}:\n{s.getvalue()}")
        return result
    return wrapper
```

## Best Practices

1. **Error Handling**
   - Log errors with context
   - Implement proper fallbacks
   - Monitor error rates
   - Use structured logging

2. **Performance Monitoring**
   - Track key metrics
   - Set up alerts
   - Monitor resource usage
   - Analyze trends

3. **Debugging**
   - Use proper logging levels
   - Implement tracing
   - Profile performance
   - Monitor dependencies