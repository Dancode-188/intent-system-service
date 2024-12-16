import pytest
from unittest.mock import patch, Mock, AsyncMock
import time
from app.metrics import track_pattern_metrics, track_query_metrics

# We'll use mocks instead of redefining the metrics
@pytest.fixture
def mock_metrics():
    with patch('app.metrics.PATTERN_COUNT') as mock_pattern_count, \
         patch('app.metrics.PATTERN_CONFIDENCE') as mock_pattern_confidence, \
         patch('app.metrics.QUERY_DURATION') as mock_query_duration, \
         patch('app.metrics.QUERY_ERRORS') as mock_query_errors:
        
        # Setup the mocks
        mock_pattern_count.labels.return_value.inc = Mock()
        mock_pattern_confidence.labels.return_value.observe = Mock()
        mock_query_duration.labels.return_value.observe = Mock()
        mock_query_errors.labels.return_value.inc = Mock()
        
        yield {
            'pattern_count': mock_pattern_count,
            'pattern_confidence': mock_pattern_confidence,
            'query_duration': mock_query_duration,
            'query_errors': mock_query_errors
        }

def test_track_pattern_metrics_success(mock_metrics):
    """Test successful pattern metrics tracking"""
    pattern_type = "behavioral"
    confidence = 0.85
    
    track_pattern_metrics(pattern_type, confidence)
    
    # Verify metrics were recorded
    mock_metrics['pattern_count'].labels.assert_called_once_with(pattern_type=pattern_type)
    mock_metrics['pattern_count'].labels.return_value.inc.assert_called_once()
    
    mock_metrics['pattern_confidence'].labels.assert_called_once_with(pattern_type=pattern_type)
    mock_metrics['pattern_confidence'].labels.return_value.observe.assert_called_once_with(confidence)

def test_track_pattern_metrics_error(mock_metrics):
    """Test pattern metrics tracking with error"""
    pattern_type = "behavioral"
    confidence = 0.85
    
    # Make the metric increment raise an error
    mock_metrics['pattern_count'].labels.return_value.inc.side_effect = Exception("Test error")
    
    with patch('app.metrics.logger.error') as mock_logger:
        track_pattern_metrics(pattern_type, confidence)
        
        # Verify error was logged
        mock_logger.assert_called_once()
        assert "Error tracking pattern metrics" in mock_logger.call_args[0][0]

@pytest.mark.asyncio
async def test_track_query_metrics_success(mock_metrics):
    """Test successful query metrics tracking"""
    operation_type = "test_operation"
    
    # Create a mock function to decorate
    async def test_func():
        return "test_result"
    
    # Apply decorator
    decorated_func = track_query_metrics(operation_type)(test_func)
    
    # Mock time to simulate duration - add third value for finally block
    with patch('time.time', side_effect=[0, 0.5, 0.5]):  # Start time, end time for observe, and finally block
        result = await decorated_func()
        
        # Verify metrics were recorded
        mock_metrics['query_duration'].labels.assert_called_with(operation_type=operation_type)
        mock_metrics['query_duration'].labels.return_value.observe.assert_called_once()
        
        assert result == "test_result"

@pytest.mark.asyncio
async def test_track_query_metrics_error(mock_metrics):
    """Test query metrics tracking with error"""
    operation_type = "test_operation"
    
    # Create a mock function that raises an error
    async def failing_func():
        raise ValueError("Test error")
    
    # Apply decorator
    decorated_func = track_query_metrics(operation_type)(failing_func)
    
    # Mock time to simulate slow query
    with patch('time.time', side_effect=[0, 2.0]), \
         patch('app.metrics.logger.warning') as mock_logger:
        
        with pytest.raises(ValueError):
            await decorated_func()
        
        # Verify error metrics were recorded
        mock_metrics['query_errors'].labels.assert_called_with(
            operation_type=operation_type,
            error_type='ValueError'
        )
        mock_metrics['query_errors'].labels.return_value.inc.assert_called_once()
        
        # Verify slow query was logged
        mock_logger.assert_called_once()
        assert "Slow query detected" in mock_logger.call_args[0][0]