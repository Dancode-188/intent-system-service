import redis.asyncio as redis
from typing import Optional
from fastapi import FastAPI
from ..config import Settings
from ..db.timescale import TimescaleDBHandler
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages database and cache connections"""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.timescale_handler: Optional[TimescaleDBHandler] = None
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self._initialized = False
        self._lock = asyncio.Lock()
        self._closing = False

    async def init(self):
        """Initialize all connections with proper locking"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized or self._closing:
                return
                
            try:
                # Initialize TimescaleDB
                self.timescale_handler = TimescaleDBHandler(self.settings)
                await self.timescale_handler.initialize()
                
                # Initialize Redis pool
                try:
                    self.redis_pool = redis.ConnectionPool.from_url(
                        self.settings.REDIS_URL,
                        max_connections=self.settings.REDIS_POOL_SIZE,
                        decode_responses=True
                    )
                    
                    # Test Redis connection
                    redis_client = redis.Redis(connection_pool=self.redis_pool)
                    try:
                        await redis_client.ping()
                    finally:
                        await redis_client.aclose()
                except Exception as redis_err:
                    # Specific Redis error handling
                    raise Exception(f"Failed to initialize Redis: {str(redis_err)}")
                    
                self._initialized = True
                logger.info("Connection manager initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize connections: {e}")
                await self._cleanup()
                raise

    async def _cleanup(self):
        """Internal cleanup method"""
        try:
            if self.timescale_handler:
                await self.timescale_handler.close()
            if self.redis_pool:
                await self.redis_pool.disconnect()
        finally:
            self.timescale_handler = None
            self.redis_pool = None
            self._initialized = False
            self._closing = False

    async def close(self):
        """Close all connections with proper locking"""
        if not self._initialized:
            return
            
        async with self._lock:
            if self._closing:
                return
            self._closing = True
            await self._cleanup()

def get_timescale(app: FastAPI) -> TimescaleDBHandler:
    """Get TimescaleDB handler from app state"""
    if not app.state.connections.timescale_handler:
        raise RuntimeError("TimescaleDB connection not initialized")
    return app.state.connections.timescale_handler

def get_redis(app: FastAPI) -> redis.Redis:
    """Get Redis connection from app state"""
    if not app.state.connections.redis_pool:
        raise RuntimeError("Redis connection not initialized")
    return redis.Redis(connection_pool=app.state.connections.redis_pool)