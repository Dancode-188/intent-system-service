from typing import Optional
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from fastapi import FastAPI
from ..config import Settings
from ..db.neo4j_handler import Neo4jHandler
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages database and cache connections"""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.neo4j_handler: Optional[Neo4jHandler] = None
        self.redis_pool: Optional[ConnectionPool] = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def init(self):
        """Initialize all connections with proper locking"""
        async with self._lock:
            if self._initialized:
                return

            try:
                # Initialize Neo4j
                self.neo4j_handler = Neo4jHandler(self.settings)
                await self.neo4j_handler.connect()

                # Initialize Redis pool
                self.redis_pool = redis.ConnectionPool.from_url(
                    self.settings.REDIS_URL,
                    max_connections=self.settings.REDIS_POOL_SIZE,
                    decode_responses=True
                )
                
                # Test Redis connection
                redis_client = redis.Redis(connection_pool=self.redis_pool)
                await redis_client.ping()
                
                self._initialized = True
                logger.info("Connection manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize connections: {e}")
                await self.close()  # Cleanup any partial initialization
                raise

    async def close(self):
        """Close all connections with proper locking"""
        async with self._lock:
            try:
                if self.neo4j_handler:
                    await self.neo4j_handler.close()
                    self.neo4j_handler = None
                
                if self.redis_pool:
                    await self.redis_pool.disconnect()
                    self.redis_pool = None
                
                self._initialized = False
                logger.info("All connections closed successfully")
            except Exception as e:
                logger.error(f"Error closing connections: {e}")
                raise

    async def check_health(self) -> dict:
        """Check health of all connections"""
        health_status = {
            "neo4j": "unavailable",
            "redis": "unavailable",
            "initialized": self._initialized
        }

        try:
            if self.neo4j_handler:
                await self.neo4j_handler.execute_query("RETURN 1", {})
                health_status["neo4j"] = "healthy"
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")

        try:
            if self.redis_pool:
                redis_client = redis.Redis(connection_pool=self.redis_pool)
                await redis_client.ping()
                health_status["redis"] = "healthy"
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")

        return health_status

def get_neo4j(app: FastAPI) -> Neo4jHandler:
    """Get Neo4j handler from app state"""
    if not app.state.connections.neo4j_handler:
        raise RuntimeError("Neo4j connection not initialized")
    return app.state.connections.neo4j_handler

def get_redis(app: FastAPI) -> redis.Redis:
    """Get Redis connection from app state"""
    if not app.state.connections.redis_pool:
        raise RuntimeError("Redis connection not initialized")
    return redis.Redis(connection_pool=app.state.connections.redis_pool)