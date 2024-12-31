import pytest
import asyncpg
from app.config import Settings
from datetime import datetime, timedelta
from app.db.timescale import TimescaleDBHandler

@pytest.mark.asyncio
async def test_store_prediction(db_handler: TimescaleDBHandler, mock_pool):
    """Test storing prediction data."""
    _, conn = mock_pool
    prediction_data = {
        "prediction_id": "test_pred_1",
        "user_id": "test_user",
        "context_id": "test_context",
        "prediction_type": "short_term",
        "predictions": [
            {"action": "test_action", "probability": 0.9}
        ],
        "confidence": 0.9,
        "metadata": {"test_key": "test_value"}
    }
    
    # Store prediction
    await db_handler.store_prediction(**prediction_data)
    
    # Verify execute was called with the INSERT query
    insert_calls = [
        call for call in conn.execute.call_args_list 
        if "INSERT INTO predictions" in str(call)
    ]
    assert len(insert_calls) == 1
    call_args = insert_calls[0][0]
    assert prediction_data["prediction_id"] == call_args[1]

@pytest.mark.asyncio
async def test_store_metric(db_handler: TimescaleDBHandler, mock_pool):
    """Test storing prediction metrics."""
    _, conn = mock_pool
    metric_data = {
        "prediction_id": "test_pred_1",
        "metric_name": "test_metric",
        "metric_value": 0.95,
        "tags": {"test_tag": "test_value"}
    }
    
    # Set up mock return values
    mock_metric = {
        "time": datetime.utcnow(),
        "prediction_id": metric_data["prediction_id"],
        "metric_name": metric_data["metric_name"],
        "metric_value": metric_data["metric_value"],
        "tags": metric_data["tags"]
    }
    conn.fetch.return_value = [mock_metric]
    
    # Store metric
    await db_handler.store_metric(**metric_data)
    
    # Retrieve and verify
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=5)
    
    metrics = await db_handler.get_metrics(
        start_time=start_time,
        end_time=end_time,
        metric_name="test_metric"
    )
    
    assert len(metrics) == 1
    assert metrics[0]["metric_value"] == metric_data["metric_value"]

@pytest.mark.asyncio 
async def test_get_nonexistent_prediction(db_handler: TimescaleDBHandler, mock_pool):
    """Test retrieving non-existent prediction."""
    _, conn = mock_pool
    conn.fetchrow.return_value = None
    
    result = await db_handler.get_prediction("nonexistent_id")
    assert result is None

@pytest.mark.asyncio
async def test_database_connection_error(test_settings):
    """Test database connection error handling."""
    # Use invalid connection URL
    test_settings.TIMESCALE_URL = "postgresql://invalid:invalid@localhost:5432/invalid"
    
    handler = TimescaleDBHandler(test_settings)
    
    with pytest.raises(Exception):
        await handler.initialize()

@pytest.mark.asyncio
async def test_create_tables_without_pool():
    """Test _create_tables with uninitialized pool."""
    handler = TimescaleDBHandler(Settings(TIMESCALE_URL="postgresql://unused"))
    # Don't initialize so pool remains None
    
    with pytest.raises(RuntimeError, match="Database pool not initialized"):
        await handler._create_tables()

@pytest.mark.asyncio
async def test_hypertable_exists(db_handler: TimescaleDBHandler, mock_pool, caplog):
    """Test handling of existing hypertable."""
    _, conn = mock_pool
    
    # Mock execute calls for all SQL statements
    conn.execute.side_effect = [
        None,  # CREATE TABLE predictions
        None,  # CREATE TABLE prediction_metrics
        asyncpg.InvalidSchemaNameError()  # create_hypertable
    ]
    
    # Reset call count from initialization
    conn.execute.reset_mock()
    
    # Execute tables creation
    await db_handler._create_tables()
    
    # Verify execute calls and warning log
    assert conn.execute.call_count == 3
    assert "Hypertable already exists" in caplog.text