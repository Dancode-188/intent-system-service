from neo4j import AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from typing import Optional, Any, Dict
import logging
import asyncio
from ..config import Settings

logger = logging.getLogger(__name__)

class Neo4jHandler:
    """
    Handles Neo4j database connections with retry logic and failover
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.driver = None
        self.max_retries = 3
        self.retry_delay = 1  # seconds

    async def connect(self) -> None:
        """
        Establish connection to Neo4j with retry logic
        """
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                if not self.driver:
                    self.driver = AsyncGraphDatabase.driver(
                        self.settings.NEO4J_URI,
                        auth=(self.settings.NEO4J_USER, self.settings.NEO4J_PASSWORD),
                        max_connection_lifetime=200
                    )
                # Verify connection
                await self.driver.verify_connectivity()
                logger.info("Successfully connected to Neo4j")
                return
            except ServiceUnavailable as e:
                retry_count += 1
                if retry_count == self.max_retries:
                    logger.error(f"Failed to connect to Neo4j after {self.max_retries} attempts")
                    raise ConnectionError(f"Could not connect to Neo4j: {str(e)}")
                logger.warning(f"Neo4j connection attempt {retry_count} failed, retrying...")
                await asyncio.sleep(self.retry_delay * retry_count)

    async def get_session(self) -> AsyncSession:
        """
        Get a Neo4j session with automatic reconnection
        """
        if not self.driver:
            await self.connect()
        # Since AsyncSession already supports async context manager,
        # we can just return it directly
        return self.driver.session()

    async def execute_query(
        self,
        query: str,
        params: Dict[str, Any],
        retry_count: int = 0
    ) -> Optional[Any]:
        """
        Execute a Neo4j query with retry logic
        """
        try:
            session = await self.get_session()
            async with session:
                result = await session.run(query, params)
                return await result.single()
        except (ServiceUnavailable, SessionExpired) as e:
            if retry_count >= self.max_retries:
                logger.error(f"Query failed after {self.max_retries} retries")
                raise  # Re-raise the original exception
            
            logger.warning(f"Query attempt {retry_count + 1} failed, retrying...")
            await asyncio.sleep(self.retry_delay * (retry_count + 1))
            return await self.execute_query(query, params, retry_count + 1)

    async def close(self) -> None:
        """
        Close Neo4j connection
        """
        if self.driver:
            await self.driver.close()
            self.driver = None
            logger.info("Neo4j connection closed")