from typing import Optional, Any, Dict, List
import asyncpg
import logging
from datetime import datetime
from ..config import Settings

logger = logging.getLogger(__name__)

class TimescaleDBHandler:
    """
    Handler for TimescaleDB operations with connection pooling
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database connection pool"""
        try:
            if not self._initialized:
                self.pool = await asyncpg.create_pool(
                    dsn=self.settings.TIMESCALE_URL,
                    min_size=5,
                    max_size=self.settings.TIMESCALE_POOL_SIZE
                )
                
                # Create tables if they don't exist
                await self._create_tables()
                self._initialized = True
                logger.info("TimescaleDB connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize TimescaleDB: {e}")
            raise

    async def _create_tables(self) -> None:
        """Create necessary tables and hypertables"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
            
        async with self.pool.acquire() as conn:
            # Create predictions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    predictions JSONB NOT NULL,
                    confidence FLOAT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            # Create hypertable for time-series data
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS prediction_metrics (
                    time TIMESTAMPTZ NOT NULL,
                    prediction_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value FLOAT NOT NULL,
                    tags JSONB
                );
            """)
            
            try:
                await conn.execute("""
                    SELECT create_hypertable('prediction_metrics', 'time', 
                        if_not_exists => TRUE);
                """)
            except asyncpg.InvalidSchemaNameError:
                logger.warning("Hypertable already exists")

    async def store_prediction(
        self,
        prediction_id: str,
        user_id: str,
        context_id: str,
        prediction_type: str,
        predictions: Dict[str, Any],
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store prediction results"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO predictions (
                    prediction_id, user_id, context_id, prediction_type,
                    predictions, confidence, metadata, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, prediction_id, user_id, context_id, prediction_type,
                predictions, confidence, metadata, datetime.utcnow())

    async def get_prediction(self, prediction_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific prediction"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT * FROM predictions WHERE prediction_id = $1
            """, prediction_id)
            
            if record:
                return dict(record)
            return None

    async def store_metric(
        self,
        prediction_id: str,
        metric_name: str,
        metric_value: float,
        tags: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store prediction metrics"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO prediction_metrics (
                    time, prediction_id, metric_name, metric_value, tags
                ) VALUES ($1, $2, $3, $4, $5)
            """, datetime.utcnow(), prediction_id, metric_name, metric_value, tags)

    async def get_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve metrics for a time range"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM prediction_metrics 
                WHERE time BETWEEN $1 AND $2
            """
            params = [start_time, end_time]
            
            if metric_name:
                query += " AND metric_name = $3"
                params.append(metric_name)
                
            records = await conn.fetch(query, *params)
            return [dict(record) for record in records]

    async def get_historical_predictions(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical predictions for a user"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT * FROM predictions 
                WHERE user_id = $1 
                AND created_at BETWEEN $2 AND $3
                ORDER BY created_at DESC
            """, user_id, start_time, end_time)
            return [dict(record) for record in records]

    async def close(self) -> None:
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("TimescaleDB connection closed")