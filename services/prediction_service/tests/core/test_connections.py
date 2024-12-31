import pytest
import asyncio
from fastapi import FastAPI
from unittest.mock import AsyncMock, patch
import redis.asyncio as redis
from app.core.connections import ConnectionManager, get_timescale, get_redis
from app.core.exceptions import DatabaseError
from app.config import get_settings

# Mock the database and Redis connections
@pytest.fixture
async def mock_db_handler():
    """Mock TimescaleDB handler."""
    mock = AsyncMock()
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()
    return mock

@pytest.fixture
async def mock_redis_pool():
    """Mock Redis connection pool with proper async context manager support."""
    mock = AsyncMock()
    mock.disconnect = AsyncMock()
    
    # Create proper async Redis client mock
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock()
    redis_client.__aenter__ = AsyncMock(return_value=redis_client)
    redis_client.__aexit__ = AsyncMock()
    
    # Configure connection pool mock
    mock.connection_kwargs = {"protocol": 3}
    mock.Redis = AsyncMock(return_value=redis_client)
    
    return mock

@pytest.fixture
async def mock_redis_client(mock_redis_pool):
    """Mock Redis client for direct access."""
    return mock_redis_pool.Redis.return_value

@pytest.mark.asyncio
async def test_connection_manager_initialization(test_settings, mock_db_handler, mock_redis_pool, mock_redis_client):
    """Test successful connection manager initialization."""
    async with asyncio.timeout(2):
        with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
             patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
            
            manager = ConnectionManager(test_settings)
            await manager.init()
            
            assert manager._initialized
            assert manager.timescale_handler is not None
            assert manager.redis_pool is not None
            
            mock_db_handler.initialize.assert_called_once()
            # Properly await Redis client operations
            redis_client = mock_redis_pool.Redis.return_value
            await redis_client.ping()
            await redis_client.aclose()
            
            await manager.close()

@pytest.mark.asyncio
async def test_connection_manager_double_initialization(test_settings, mock_db_handler, mock_redis_pool):
    """Test double initialization handling."""
    async with asyncio.timeout(2):  # 2 second timeout
        with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
            patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
            
            manager = ConnectionManager(test_settings)
            await manager.init()
            await manager.init()  # Second initialization
            
            assert manager._initialized
            # Should only be called once
            mock_db_handler.initialize.assert_called_once()
            await manager.close()

@pytest.mark.asyncio
async def test_connection_manager_close(test_settings, mock_db_handler, mock_redis_pool):
    """Test connection cleanup."""
    async with asyncio.timeout(2):  # 2 second timeout
        with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
            patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
            
            manager = ConnectionManager(test_settings)
            await manager.init()
            await manager.close()
            
            assert not manager._initialized
            assert manager.timescale_handler is None
            assert manager.redis_pool is None
            mock_db_handler.close.assert_called_once()
            mock_redis_pool.disconnect.assert_called_once()

@pytest.mark.asyncio
async def test_redis_connection_failure(test_settings, mock_db_handler):
    """Test Redis connection failure handling."""
    def raise_redis_error(*args, **kwargs):
        raise redis.RedisError("Connection failed")
    
    with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
         patch('redis.asyncio.ConnectionPool.from_url', side_effect=raise_redis_error):
        
        manager = ConnectionManager(test_settings)
        with pytest.raises(Exception) as exc_info:
            await manager.init()
        
        assert "Failed to initialize Redis" in str(exc_info.value)
        assert not manager._initialized
        mock_db_handler.close.assert_called_once()

@pytest.mark.asyncio
async def test_db_connection_failure(test_settings, mock_db_handler):
    """Test database connection failure handling."""
    async with asyncio.timeout(2):  # 2 second timeout
        mock_db_handler.initialize.side_effect = Exception("DB connection failed")
        
        with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler):
            manager = ConnectionManager(test_settings)
            with pytest.raises(Exception):
                await manager.init()
            
            assert not manager._initialized

@pytest.mark.asyncio
async def test_connection_close_error_handling(test_settings, mock_db_handler, mock_redis_pool):
    """Test error handling during connection cleanup."""
    mock_db_handler.close.side_effect = Exception("Close failed")
    mock_redis_pool.disconnect.side_effect = Exception("Disconnect failed")
    
    with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
         patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
        
        manager = ConnectionManager(test_settings)
        await manager.init()
        
        # Should raise the first error encountered
        with pytest.raises(Exception) as exc_info:
            await manager.close()
        
        assert "Close failed" in str(exc_info.value)
        assert not manager._initialized

@pytest.mark.asyncio
async def test_concurrent_initialization(test_settings, mock_db_handler, mock_redis_pool):
    """Test concurrent initialization handling."""
    async with asyncio.timeout(2):  # 2 second timeout
        with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
            patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
            
            manager = ConnectionManager(test_settings)
            
            # Simulate concurrent initialization
            await asyncio.gather(
                manager.init(),
                manager.init(),
                manager.init()
            )
            
            assert manager._initialized
            mock_db_handler.initialize.assert_called_once()
            await manager.close()

@pytest.mark.asyncio
async def test_connection_cleanup(test_settings, mock_db_handler, mock_redis_pool):
    """Test connection cleanup scenarios"""
    with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
         patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
        
        manager = ConnectionManager(test_settings)
        await manager.init()
        
        await manager.close()
        
        assert not manager._initialized
        assert manager.timescale_handler is None
        assert manager.redis_pool is None
        mock_db_handler.close.assert_called_once()
        mock_redis_pool.disconnect.assert_called_once()

@pytest.mark.asyncio
async def test_early_returns(test_settings, mock_db_handler, mock_redis_pool):
    """Test early return conditions in init and close methods."""
    with patch('app.core.connections.TimescaleDBHandler', return_value=mock_db_handler), \
         patch('redis.asyncio.ConnectionPool.from_url', return_value=mock_redis_pool):
        
        manager = ConnectionManager(test_settings)
        
        # Test early return when already initialized
        manager._initialized = True
        await manager.init()  # Should return early
        mock_db_handler.initialize.assert_not_called()
        
        # Test early return when closing during init
        manager._initialized = False
        manager._closing = True
        await manager.init()  # Should hit line 28 return
        mock_db_handler.initialize.assert_not_called()
        
        # Test early return when not initialized for close
        manager._initialized = False
        manager._closing = False
        await manager.close()  # Should return early
        mock_db_handler.close.assert_not_called()
        
        # Test early return when closing during close
        manager._initialized = True
        manager._closing = True
        await manager.close()  # Should return early
        mock_db_handler.close.assert_not_called()

@pytest.mark.asyncio
async def test_get_timescale_uninitialized():
    """Test get_timescale when handler is not initialized."""
    app = FastAPI()
    app.state.connections = ConnectionManager(get_settings())
    app.state.connections.timescale_handler = None
    
    with pytest.raises(RuntimeError) as exc_info:
        get_timescale(app)
    assert "TimescaleDB connection not initialized" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_timescale_initialized(test_settings, mock_db_handler):
    """Test get_timescale when handler is initialized."""
    app = FastAPI()
    app.state.connections = ConnectionManager(test_settings)
    app.state.connections.timescale_handler = mock_db_handler
    
    handler = get_timescale(app)
    assert handler == mock_db_handler

@pytest.mark.asyncio
async def test_get_redis_uninitialized():
    """Test get_redis when pool is not initialized."""
    app = FastAPI()
    app.state.connections = ConnectionManager(get_settings())
    app.state.connections.redis_pool = None
    
    with pytest.raises(RuntimeError) as exc_info:
        get_redis(app)
    assert "Redis connection not initialized" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_redis_initialized(test_settings, mock_redis_pool):
    """Test get_redis when pool is initialized."""
    app = FastAPI()
    app.state.connections = ConnectionManager(test_settings)
    app.state.connections.redis_pool = mock_redis_pool
    
    redis_client = get_redis(app)
    assert isinstance(redis_client, redis.Redis)
    assert redis_client.connection_pool == mock_redis_pool