import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from neo4j import AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import ServiceUnavailable, SessionExpired
import asyncio

from app.config import Settings
from app.db.neo4j_handler import Neo4jHandler

@pytest.mark.unit
class TestNeo4jHandler:
    @pytest.fixture
    def settings(self):
        """Test settings"""
        return Settings(
            NEO4J_URI="bolt://test:7687",
            NEO4J_USER="test",
            NEO4J_PASSWORD="test"
        )

    @pytest.fixture
    def mock_driver(self):
        """Mock Neo4j driver"""
        driver = AsyncMock(spec=AsyncGraphDatabase.driver)
        driver.verify_connectivity = AsyncMock()
        # Instead of making session itself async, make it return the session directly
        driver.session = MagicMock()  # Change this from AsyncMock to MagicMock
        driver.close = AsyncMock()
        return driver

    @pytest.fixture
    async def mock_session(self):
        """Mock Neo4j session"""
        # Create a MagicMock for the base session
        session = MagicMock(spec=AsyncSession)
        
        # Configure async context manager methods
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()
        
        # Configure async methods
        session.run = AsyncMock()
        session.close = AsyncMock()
        
        # Configure result
        result = AsyncMock()
        result.single = AsyncMock(return_value={"result": "test"})
        session.run.return_value = result
        
        return session

    @pytest.fixture
    def handler(self, settings):
        """Neo4j handler instance"""
        return Neo4jHandler(settings)

    async def test_connect_success(self, handler, mock_driver):
        """Test successful connection to Neo4j"""
        with patch('neo4j.AsyncGraphDatabase.driver', return_value=mock_driver):
            await handler.connect()
            
            assert handler.driver == mock_driver
            mock_driver.verify_connectivity.assert_called_once()

    async def test_connect_retry_success(self, handler, mock_driver):
        """Test successful connection after retry"""
        mock_driver.verify_connectivity.side_effect = [
            ServiceUnavailable("First attempt failed"),
            None  # Second attempt succeeds
        ]
        
        with patch('neo4j.AsyncGraphDatabase.driver', return_value=mock_driver):
            await handler.connect()
            
            assert handler.driver == mock_driver
            assert mock_driver.verify_connectivity.call_count == 2

    async def test_connect_all_retries_failed(self, handler, mock_driver):
        """Test connection failure after all retries"""
        mock_driver.verify_connectivity.side_effect = ServiceUnavailable("Connection failed")
        
        with patch('neo4j.AsyncGraphDatabase.driver', return_value=mock_driver):
            with pytest.raises(ConnectionError) as exc_info:
                await handler.connect()
            
            assert "Could not connect to Neo4j" in str(exc_info.value)
            assert mock_driver.verify_connectivity.call_count == handler.max_retries

    async def test_get_session_with_connection(self, handler, mock_driver, mock_session):
        """Test getting session with existing connection"""
        handler.driver = mock_driver
        mock_driver.session.return_value = mock_session
        
        session = await handler.get_session()
        assert session == mock_session
        mock_driver.session.assert_called_once()

    async def test_get_session_without_connection(self, handler, mock_driver, mock_session):
        """Test getting session when not connected"""
        with patch('neo4j.AsyncGraphDatabase.driver', return_value=mock_driver):
            mock_driver.session.return_value = mock_session
            # Configure session context manager
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            
            session = await handler.get_session()
            assert session == mock_session
            mock_driver.verify_connectivity.assert_called_once()

    async def test_execute_query_success(self, handler, mock_driver, mock_session):
        """Test successful query execution"""
        handler.driver = mock_driver
        mock_driver.session.return_value = mock_session
        
        query = "MATCH (n) RETURN n"
        params = {"param": "value"}
        
        # Configure the mock session's run method to return a mock result
        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value={"result": "test"})
        mock_session.run.return_value = result_mock
        
        result = await handler.execute_query(query, params)
        
        assert result == {"result": "test"}
        mock_session.run.assert_called_once_with(query, params)

    async def test_execute_query_retry_success(self, handler, mock_driver, mock_session):
        """Test successful query execution after retry"""
        handler.driver = mock_driver
        mock_driver.session.return_value = mock_session
        
        # Setup async context manager
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        
        # First call raises error
        error_result = AsyncMock()
        error_result.single = AsyncMock(side_effect=ServiceUnavailable("First attempt failed"))
        
        # Second call succeeds
        success_result = AsyncMock()
        success_result.single = AsyncMock(return_value={"result": "test"})
        
        # Configure mock to fail first, then succeed
        mock_session.run = AsyncMock(side_effect=[error_result, success_result])
        
        result = await handler.execute_query("MATCH (n) RETURN n", {})
        
        assert result == {"result": "test"}
        assert mock_session.run.call_count == 2

    async def test_execute_query_all_retries_failed(self, handler, mock_driver, mock_session):
        """Test query failure after all retries"""
        handler.driver = mock_driver
        mock_driver.session.return_value = mock_session

        # Configure session run to always raise ServiceUnavailable
        error = ServiceUnavailable("Query failed")
        mock_session.run.side_effect = error
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        # Should raise ServiceUnavailable after max retries
        with pytest.raises(ServiceUnavailable) as exc_info:
            await handler.execute_query("MATCH (n) RETURN n", {})
        
        # Verify error message and call count
        assert str(exc_info.value) == "Query failed"
        # Should be called max_retries + 1 times (initial attempt + retries)
        assert mock_session.run.call_count == handler.max_retries + 1

    async def test_close_success(self, handler, mock_driver):
        """Test successful connection closure"""
        handler.driver = mock_driver
        
        await handler.close()
        
        assert handler.driver is None
        mock_driver.close.assert_called_once()

    async def test_close_without_driver(self, handler):
        """Test closing when no driver exists"""
        handler.driver = None
        
        await handler.close()  # Should not raise any exception

    async def test_session_context_manager(self, handler, mock_driver, mock_session):
        """Test session context manager usage"""
        handler.driver = mock_driver
        mock_driver.session.return_value = mock_session
        
        async with await handler.get_session() as session:
            result = await session.run("MATCH (n) RETURN n")
            assert await result.single() == {"result": "test"}