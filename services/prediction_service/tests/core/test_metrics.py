import pytest
from unittest.mock import patch, AsyncMock
import time
from app.core.metrics import track_service_request

@pytest.mark.asyncio
async def test_service_request_error_tracking():
    """Test error tracking in service requests."""
    # Test parameters
    service = "test_service"
    endpoint = "test_endpoint"
    test_error = ValueError("Test error")
    
    # Create a mock function that raises an error
    @track_service_request(service=service, endpoint=endpoint)
    async def failing_func():
        raise test_error
    
    # Mock the metrics
    with patch('app.core.metrics.SERVICE_REQUEST_COUNT.labels') as mock_count, \
         patch('app.core.metrics.SERVICE_REQUEST_DURATION.labels') as mock_duration:
        
        # Setup mock returns
        mock_count.return_value.inc = AsyncMock()
        mock_duration.return_value.observe = AsyncMock()
        
        # Execute test - error should propagate
        with pytest.raises(ValueError) as exc_info:
            await failing_func()
        
        # Verify error metrics were recorded
        mock_count.assert_called_with(
            service=service,
            endpoint=endpoint,
            status="error"
        )
        mock_count.return_value.inc.assert_called_once()
        
        # Verify duration was recorded
        mock_duration.assert_called_with(
            service=service,
            endpoint=endpoint
        )
        mock_duration.return_value.observe.assert_called_once()
        
        # Verify original error was propagated
        assert exc_info.value is test_error