import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from fastapi import FastAPI
import asyncio
from app.core.connections import ConnectionManager, get_neo4j, get_redis  # Added imports
from app.config import Settings
from app.db.neo4j_handler import Neo4jHandler

@pytest.mark.unit
class TestConnectionManager:
    @pytest.fixture
    def settings(self):
        """Test settings"""
        return Settings(
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
            REDIS_URL="redis://localhost:6379/0",
            REDIS_POOL_SIZE=20
        )

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j handler with proper async methods"""
        mock = AsyncMock()
        mock.connect = AsyncMock()
        mock.close = AsyncMock()
        mock.execute_query = AsyncMock()
        # Ensure the close method doesn't hang
        mock.close.return_value = None
        return mock

    @pytest.fixture
    def mock_redis_pool(self):
        """Mock Redis connection pool"""
        mock = MagicMock(spec=ConnectionPool)
        mock.disconnect = AsyncMock()
        return mock

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client"""
        mock = AsyncMock(spec=redis.Redis)
        mock.ping = AsyncMock()
        return mock

    @pytest.fixture
    def connection_manager(self, settings):
        """Connection manager instance"""
        return ConnectionManager(settings)

    async def test_init_success(self, connection_manager, mock_neo4j, mock_redis_pool, mock_redis_client):
        """Test successful initialization of connections"""
        with patch('app.core.connections.Neo4jHandler', return_value=mock_neo4j), \
             patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool), \
             patch('redis.asyncio.Redis', return_value=mock_redis_client):
            
            await connection_manager.init()
            
            assert connection_manager._initialized is True
            mock_neo4j.connect.assert_called_once()
            mock_redis_client.ping.assert_called_once()

    async def test_init_neo4j_failure(self, connection_manager, mock_neo4j, mock_redis_pool, mock_redis_client):
        """Test initialization when Neo4j connection fails"""
        
        # Create a proper async context manager mock for the lock
        mock_lock = AsyncMock()
        mock_lock.__aenter__.return_value = None
        mock_lock.__aexit__.return_value = None
        connection_manager._lock = mock_lock
        
        # Configure Neo4jHandler mock to fail
        mock_handler = AsyncMock(spec=Neo4jHandler)
        mock_handler.connect.side_effect = Exception("Neo4j connection failed")
        mock_handler.close = AsyncMock()
        
        # Set up patches
        with patch('app.core.connections.Neo4jHandler', return_value=mock_handler), \
            patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool), \
            patch('redis.asyncio.Redis', return_value=mock_redis_client):
            
            try:
                with pytest.raises(Exception) as exc_info:
                    await connection_manager.init()
                print(f"Init call completed with exception: {exc_info.value}")
                
                assert "Neo4j connection failed" in str(exc_info.value)
                assert not connection_manager._initialized
                
            finally:
                # Clean up without using lock
                if connection_manager.neo4j_handler:
                    await connection_manager.neo4j_handler.close()
                if connection_manager.redis_pool:
                    await connection_manager.redis_pool.disconnect()

    async def test_init_redis_failure(self, connection_manager, mock_neo4j, mock_redis_pool, mock_redis_client):
        """Test initialization when Redis connection fails"""
        
        # Create a proper async context manager mock for the lock
        mock_lock = AsyncMock()
        mock_lock.__aenter__.return_value = None
        mock_lock.__aexit__.return_value = None
        connection_manager._lock = mock_lock
        
        # Configure Redis client mock to fail
        mock_redis_client.ping.side_effect = redis.RedisError("Redis connection failed")
        
        # Set up patches
        with patch('app.core.connections.Neo4jHandler', return_value=mock_neo4j), \
            patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool), \
            patch('redis.asyncio.Redis', return_value=mock_redis_client):
            
            try:
                with pytest.raises(Exception) as exc_info:
                    await connection_manager.init()
                print(f"Init call completed with exception: {exc_info.value}")
                
                assert "Redis connection failed" in str(exc_info.value)
                assert not connection_manager._initialized
                mock_neo4j.connect.assert_called_once()
                mock_redis_client.ping.assert_called_once()
                
            finally:
                # Clean up without using lock
                if connection_manager.neo4j_handler:
                    await connection_manager.neo4j_handler.close()
                if connection_manager.redis_pool:
                    await connection_manager.redis_pool.disconnect()

    async def test_init_already_initialized(self, connection_manager):
        """Test initialization when already initialized"""
        connection_manager._initialized = True
        await connection_manager.init()  # Should return immediately
        assert connection_manager._initialized is True

    async def test_close_success(self, connection_manager, mock_neo4j, mock_redis_pool):
        """Test successful connection cleanup"""
        connection_manager.neo4j_handler = mock_neo4j
        connection_manager.redis_pool = mock_redis_pool
        connection_manager._initialized = True
        
        await connection_manager.close()
        
        assert connection_manager._initialized is False
        assert connection_manager.neo4j_handler is None
        assert connection_manager.redis_pool is None
        mock_neo4j.close.assert_called_once()
        mock_redis_pool.disconnect.assert_called_once()

    async def test_close_with_errors(self, connection_manager, mock_neo4j, mock_redis_pool):
        """Test connection cleanup with errors"""
        # Create a proper async context manager mock for the lock
        mock_lock = AsyncMock()
        mock_lock.__aenter__.return_value = None
        mock_lock.__aexit__.return_value = None
        connection_manager._lock = mock_lock
        
        mock_neo4j.close.side_effect = Exception("Neo4j close failed")
        mock_redis_pool.disconnect.side_effect = Exception("Redis close failed")

        connection_manager.neo4j_handler = mock_neo4j
        connection_manager.redis_pool = mock_redis_pool

        with pytest.raises(Exception) as exc_info:
            await connection_manager.close()

        # Changed assertion - we're getting the original error
        assert "Neo4j close failed" in str(exc_info.value)

    async def test_check_health_all_healthy(self, connection_manager, mock_neo4j, mock_redis_pool, mock_redis_client):
        """Test health check when all connections are healthy"""
        connection_manager.neo4j_handler = mock_neo4j
        connection_manager.redis_pool = mock_redis_pool
        connection_manager._initialized = True
        
        with patch('redis.asyncio.Redis', return_value=mock_redis_client):
            health_status = await connection_manager.check_health()
        
        assert health_status["neo4j"] == "healthy"
        assert health_status["redis"] == "healthy"
        assert health_status["initialized"] is True
        mock_neo4j.execute_query.assert_called_once()
        mock_redis_client.ping.assert_called_once()

    async def test_check_health_neo4j_unhealthy(self, connection_manager, mock_neo4j, mock_redis_pool, mock_redis_client):
        """Test health check when Neo4j is unhealthy"""
        mock_neo4j.execute_query.side_effect = Exception("Neo4j health check failed")
        
        connection_manager.neo4j_handler = mock_neo4j
        connection_manager.redis_pool = mock_redis_pool
        connection_manager._initialized = True
        
        with patch('redis.asyncio.Redis', return_value=mock_redis_client):
            health_status = await connection_manager.check_health()
        
        assert health_status["neo4j"] == "unavailable"
        assert health_status["redis"] == "healthy"
        mock_neo4j.execute_query.assert_called_once()
        mock_redis_client.ping.assert_called_once()

    async def test_check_health_redis_unhealthy(self, connection_manager, mock_neo4j, mock_redis_pool, mock_redis_client):
        """Test health check when Redis is unhealthy"""
        mock_redis_client.ping.side_effect = redis.RedisError("Redis health check failed")
        
        connection_manager.neo4j_handler = mock_neo4j
        connection_manager.redis_pool = mock_redis_pool
        connection_manager._initialized = True
        
        with patch('redis.asyncio.Redis', return_value=mock_redis_client):
            health_status = await connection_manager.check_health()
        
        assert health_status["neo4j"] == "healthy"
        assert health_status["redis"] == "unavailable"
        mock_neo4j.execute_query.assert_called_once()
        mock_redis_client.ping.assert_called_once()

    async def test_check_health_uninitialized(self, connection_manager):
        """Test health check when connections are not initialized"""
        health_status = await connection_manager.check_health()
        
        assert health_status["neo4j"] == "unavailable"
        assert health_status["redis"] == "unavailable"
        assert health_status["initialized"] is False

    def test_get_neo4j_initialized(self):
        """Test getting Neo4j handler when initialized"""
        app = FastAPI()
        app.state.connections = MagicMock()
        app.state.connections.neo4j_handler = AsyncMock(spec=Neo4jHandler)
        
        handler = get_neo4j(app)
        assert handler is app.state.connections.neo4j_handler

    def test_get_neo4j_uninitialized(self):
        """Test getting Neo4j handler when uninitialized"""
        app = FastAPI()
        app.state.connections = MagicMock()
        app.state.connections.neo4j_handler = None
        
        with pytest.raises(RuntimeError) as exc_info:
            get_neo4j(app)
        assert "Neo4j connection not initialized" in str(exc_info.value)

    def test_get_redis_initialized(self):
        """Test getting Redis connection when initialized"""
        app = FastAPI()
        app.state.connections = MagicMock()
        app.state.connections.redis_pool = MagicMock(spec=ConnectionPool)
        
        client = get_redis(app)
        assert isinstance(client, redis.Redis)

    def test_get_redis_initialized(self):
        """Test getting Redis connection when initialized"""
        app = FastAPI()
        app.state.connections = MagicMock()
        
        # Create proper mock with connection_kwargs
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_pool.connection_kwargs = {}
        app.state.connections.redis_pool = mock_pool
        
        client = get_redis(app)
        assert isinstance(client, redis.Redis)

    @pytest.fixture(autouse=True)
    async def cleanup_connections(self, connection_manager):
        """Ensure connections are cleaned up after each test"""
        yield
        try:
            await connection_manager.close()
        except Exception:
            pass  # Ignore cleanup errors

    def test_get_redis_uninitialized(self):
        """Test getting Redis connection when uninitialized"""
        app = FastAPI()
        app.state.connections = MagicMock()
        app.state.connections.redis_pool = None  # Connection pool not initialized
        
        with pytest.raises(RuntimeError) as exc_info:
            get_redis(app)
        assert "Redis connection not initialized" in str(exc_info.value)