import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.health import HealthChecker
from app.config import Settings

@pytest.mark.unit
class TestHealthChecker:
    @pytest.fixture
    def settings(self):
        return Settings(
            SERVICE_NAME="test-service",
            VERSION="0.1.0"
        )
    
    @pytest.fixture
    def mock_neo4j(self):
        neo4j = AsyncMock()
        neo4j.execute_query = AsyncMock()
        return neo4j
    
    @pytest.fixture
    def health_checker(self, settings, mock_neo4j):
        return HealthChecker(settings, mock_neo4j)

    async def test_check_health_success(self, health_checker, mock_neo4j):
        """Test successful health check"""
        # Mock psutil functions
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory', return_value=MagicMock(percent=60.0)), \
             patch('psutil.disk_usage', return_value=MagicMock(percent=70.0)):
            
            result = await health_checker.check_health()
            
            assert result["status"] == "healthy"
            assert result["version"] == "0.1.0"
            assert isinstance(result["timestamp"], str)
            assert "components" in result
            
            # Check Neo4j component
            assert result["components"]["neo4j"]["status"] == "up"
            assert "message" in result["components"]["neo4j"]
            
            # Check system component
            system = result["components"]["system"]
            assert system["cpu_usage"] == 50.0
            assert system["memory_usage"] == 60.0
            assert system["disk_usage"] == 70.0

    async def test_check_health_neo4j_failure(self, health_checker, mock_neo4j):
        """Test health check when Neo4j is down"""
        mock_neo4j.execute_query.side_effect = Exception("Connection failed")
        
        # Mock psutil functions
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory', return_value=MagicMock(percent=60.0)), \
             patch('psutil.disk_usage', return_value=MagicMock(percent=70.0)):
            
            result = await health_checker.check_health()
            
            assert result["status"] == "degraded"
            assert result["version"] == "0.1.0"
            assert isinstance(result["timestamp"], str)
            
            # Check Neo4j component shows failure
            assert result["components"]["neo4j"]["status"] == "down"
            assert "Connection failed" in result["components"]["neo4j"]["message"]

    async def test_check_neo4j(self, health_checker, mock_neo4j):
        """Test Neo4j connection check specifically"""
        # Test successful connection
        result = await health_checker._check_neo4j()
        assert result["status"] == "up"
        assert result["message"] == "Connected to Neo4j"
        
        # Test failed connection
        mock_neo4j.execute_query.side_effect = Exception("Connection failed")
        result = await health_checker._check_neo4j()
        assert result["status"] == "down"
        assert "Connection failed" in result["message"]

    def test_check_system_resources(self, health_checker):
        """Test system resource check"""
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory', return_value=MagicMock(percent=60.0)), \
             patch('psutil.disk_usage', return_value=MagicMock(percent=70.0)):
            
            result = health_checker._check_system_resources()
            
            assert result["cpu_usage"] == 50.0
            assert result["memory_usage"] == 60.0
            assert result["disk_usage"] == 70.0

    async def test_health_check_extreme_values(self, health_checker, mock_neo4j):
        """Test health check with extreme resource values"""
        with patch('psutil.cpu_percent', return_value=99.9), \
             patch('psutil.virtual_memory', return_value=MagicMock(percent=95.0)), \
             patch('psutil.disk_usage', return_value=MagicMock(percent=98.0)):
            
            result = await health_checker.check_health()
            
            assert result["status"] == "healthy"  # Still healthy as Neo4j is up
            system = result["components"]["system"]
            assert system["cpu_usage"] == 99.9
            assert system["memory_usage"] == 95.0
            assert system["disk_usage"] == 98.0