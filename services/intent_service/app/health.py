from typing import Dict, Any
from datetime import datetime
import psutil
from .db.neo4j_handler import Neo4jHandler
from .config import Settings

class HealthChecker:
    def __init__(self, settings: Settings, neo4j: Neo4jHandler):
        self.settings = settings
        self.neo4j = neo4j

    async def check_health(self) -> Dict[str, Any]:
        """
        Comprehensive health check of the service
        """
        neo4j_health = await self._check_neo4j()
        system_health = self._check_system_resources()
        
        status = "healthy" if neo4j_health["status"] == "up" else "degraded"
        
        return {
            "status": status,
            "version": self.settings.VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "neo4j": neo4j_health,
                "system": system_health
            }
        }

    async def _check_neo4j(self) -> Dict[str, str]:
        """Check Neo4j connection health"""
        try:
            # Simple query to verify database connection
            await self.neo4j.execute_query("RETURN 1", {})
            return {
                "status": "up",
                "message": "Connected to Neo4j"
            }
        except Exception as e:
            return {
                "status": "down",
                "message": f"Neo4j connection error: {str(e)}"
            }

    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        return {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }