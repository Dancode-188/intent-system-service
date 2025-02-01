# Redis Configuration and Usage Guide

## Overview

The Context Service uses Redis for rate limiting and optional caching of frequently accessed embeddings. This document details the Redis implementation, configuration, and usage patterns.

## Configuration

### Redis Settings

```python
# config.py
class Settings(BaseSettings):
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_POOL_SIZE: int = 20
    REDIS_TIMEOUT: int = 10
    REDIS_RETRY_ATTEMPTS: int = 3

    # Rate Limiting
    RATE_LIMIT_WINDOW: int = 60  # seconds
    MAX_REQUESTS_PER_WINDOW: int = 100
```

### Connection Management

```python
class RedisManager:
    """Redis connection manager"""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: Optional[ConnectionPool] = None
        self._lock = asyncio.Lock()

    async def get_connection(self) -> redis.Redis:
        """Get Redis connection from pool"""
        if not self.pool:
            await self.initialize_pool()

        return redis.Redis(
            connection_pool=self.pool,
            decode_responses=True
        )

    async def initialize_pool(self):
        """Initialize Redis connection pool"""
        async with self._lock:
            if not self.pool:
                self.pool = redis.ConnectionPool(
                    host=self.settings.REDIS_HOST,
                    port=self.settings.REDIS_PORT,
                    db=self.settings.REDIS_DB,
                    password=self.settings.REDIS_PASSWORD,
                    max_connections=self.settings.REDIS_POOL_SIZE,
                    decode_responses=True
                )

    async def close(self):
        """Close Redis connections"""
        if self.pool:
            await self.pool.disconnect()
            self.pool = None
```

## Rate Limiting Implementation

### Rate Limiter Class

```python
class RateLimiter:
    """Rate limiting implementation"""
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        client_id: str,
        limit: int = 100,
        window: int = 60
    ) -> bool:
        """
        Check if request is within rate limits

        Args:
            client_id: Unique client identifier
            limit: Maximum requests per window
            window: Time window in seconds

        Returns:
            bool: True if request is allowed, False otherwise
        """
        key = f"rate_limit:{client_id}"

        async with self.redis.pipeline() as pipe:
            try:
                # Get current count
                current = await pipe.get(key)

                if not current:
                    # First request in window
                    await pipe.setex(key, window, 1)
                    return True

                current = int(current)
                if current >= limit:
                    return False

                # Increment counter
                await pipe.incr(key)
                return True

            except redis.RedisError as e:
                logger.error(f"Rate limit check failed: {e}")
                # Default to allowing request on Redis error
                return True
```

### Rate Limit Error Handling

```python
class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, client_id: str, limit: int, window: int):
        self.client_id = client_id
        self.limit = limit
        self.window = window
        super().__init__(
            f"Rate limit exceeded for {client_id}: "
            f"{limit} requests per {window} seconds"
        )
```

## Embedding Cache Implementation

### Cache Manager

```python
class EmbeddingCache:
    """Cache manager for embeddings"""
    def __init__(self, redis_client: redis.Redis, ttl: int = 3600):
        self.redis = redis_client
        self.ttl = ttl

    async def get_embedding(
        self,
        context_id: str
    ) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        try:
            data = await self.redis.get(f"embedding:{context_id}")
            if data:
                return np.frombuffer(data, dtype=np.float32)
            return None
        except redis.RedisError as e:
            logger.error(f"Cache retrieval failed: {e}")
            return None

    async def set_embedding(
        self,
        context_id: str,
        embedding: np.ndarray
    ) -> bool:
        """Store embedding in cache"""
        try:
            data = embedding.astype(np.float32).tobytes()
            return await self.redis.setex(
                f"embedding:{context_id}",
                self.ttl,
                data
            )
        except redis.RedisError as e:
            logger.error(f"Cache storage failed: {e}")
            return False

    async def delete_embedding(self, context_id: str) -> bool:
        """Remove embedding from cache"""
        try:
            return await self.redis.delete(f"embedding:{context_id}")
        except redis.RedisError as e:
            logger.error(f"Cache deletion failed: {e}")
            return False
```

## Monitoring and Metrics

### Redis Health Check

```python
async def check_redis_health(redis_client: redis.Redis) -> Dict[str, str]:
    """Check Redis connection health"""
    try:
        await redis_client.ping()
        info = await redis_client.info()
        return {
            "status": "healthy",
            "connected_clients": info["connected_clients"],
            "used_memory": info["used_memory_human"],
            "last_save_time": datetime.fromtimestamp(
                info["rdb_last_save_time"]
            ).isoformat()
        }
    except redis.RedisError as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

### Performance Metrics

```python
class RedisMetrics:
    """Redis performance metrics collection"""
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect Redis performance metrics"""
        try:
            info = await self.redis.info()
            return {
                "hits": info["keyspace_hits"],
                "misses": info["keyspace_misses"],
                "hit_rate": (
                    info["keyspace_hits"] /
                    (info["keyspace_hits"] + info["keyspace_misses"])
                ),
                "memory_used": info["used_memory"],
                "peak_memory": info["used_memory_peak"],
                "clients": info["connected_clients"],
                "operations": {
                    "commands_processed": info["total_commands_processed"],
                    "expired_keys": info["expired_keys"],
                    "evicted_keys": info["evicted_keys"]
                }
            }
        except redis.RedisError as e:
            logger.error(f"Metrics collection failed: {e}")
            return {}
```

## Best Practices

### 1. Connection Management

- Use connection pooling
- Implement proper error handling
- Close connections properly
- Monitor connection pool usage

### 2. Key Management

```python
class KeyManagement:
    """Redis key management practices"""
    @staticmethod
    def generate_key(prefix: str, identifier: str) -> str:
        """Generate consistent Redis key"""
        return f"{prefix}:{identifier}"

    @staticmethod
    def parse_key(key: str) -> Tuple[str, str]:
        """Parse Redis key into components"""
        prefix, identifier = key.split(':', 1)
        return prefix, identifier
```

### 3. Error Handling

```python
async def redis_operation(func: Callable) -> Any:
    """Decorator for Redis operations with error handling"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            raise
        except redis.RedisError as e:
            logger.error(f"Redis operation failed: {e}")
            raise
    return wrapper
```

## Deployment Considerations

### 1. Memory Management

```python
def calculate_memory_usage(
    avg_embedding_size: int,
    num_embeddings: int,
    overhead_factor: float = 1.2
) -> int:
    """Calculate estimated Redis memory usage"""
    base_memory = avg_embedding_size * num_embeddings
    return int(base_memory * overhead_factor)
```

### 2. Backup Configuration

```python
def configure_persistence(redis_client: redis.Redis):
    """Configure Redis persistence settings"""
    redis_client.config_set('save', '900 1 300 10 60 10000')
    redis_client.config_set('stop-writes-on-bgsave-error', 'yes')
    redis_client.config_set('rdbcompression', 'yes')
```

## Testing

```python
@pytest.mark.asyncio
async def test_rate_limiter():
    """Test rate limiting functionality"""
    redis_client = await get_redis_client()
    limiter = RateLimiter(redis_client)

    # Test within limits
    assert await limiter.check_rate_limit("test_client")

    # Test limit exceeded
    for _ in range(100):
        await limiter.check_rate_limit("test_client")
    assert not await limiter.check_rate_limit("test_client")
```

## Security Considerations

1. Authentication
2. Network security
3. Data encryption
4. Access control

## Monitoring Tips

1. Watch memory usage
2. Monitor connection pool
3. Track cache hit rates
4. Set up alerts for errors