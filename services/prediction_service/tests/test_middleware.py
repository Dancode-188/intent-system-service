import pytest
from fastapi import FastAPI, Request, Response
from unittest.mock import AsyncMock, MagicMock, patch
from prometheus_client import Counter, Histogram
from app.middleware import TimingMiddleware, SecurityHeadersMiddleware

@pytest.fixture
def app():
    """Create test FastAPI app with middleware"""
    app = FastAPI()
    app.add_middleware(TimingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    return app

@pytest.fixture
def mock_request():
    """Create mock request"""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.state = MagicMock()
    request.url = MagicMock()
    request.url.path = "/test"
    request.method = "GET"
    return request

@pytest.fixture
def mock_metrics():
    """Mock prometheus metrics"""
    with patch('app.middleware.REQUEST_COUNT') as mock_counter, \
         patch('app.middleware.REQUEST_DURATION') as mock_hist:
        
        # Setup Counter mock
        mock_counter.labels.return_value = MagicMock()
        mock_counter.labels.return_value.inc = MagicMock()
        
        # Setup Histogram mock
        mock_hist.labels.return_value = MagicMock()
        mock_hist.labels.return_value.observe = MagicMock()
        
        yield mock_counter, mock_hist

@pytest.mark.asyncio
async def test_timing_middleware(mock_metrics):
    """Test timing middleware functionality"""
    app = FastAPI()
    middleware = TimingMiddleware(app)
    
    # Create request with complete scope including headers
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],  # Empty list but present
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
    })
    
    response = Response(content="test", status_code=200)
    call_next = AsyncMock(return_value=response)
    
    # Only need to mock time.time() for the actual timing, not metrics
    with patch('time.time', side_effect=[1000.0, 1000.5]):
        result = await middleware.dispatch(request, call_next)
    
    # Verify headers
    assert "X-Process-Time" in result.headers
    assert "X-Request-ID" in result.headers
    assert result.headers["X-Request-ID"].startswith("req_")
    assert float(result.headers["X-Process-Time"]) == 0.5
    
    # Verify metrics were called
    counter, hist = mock_metrics
    counter.labels.assert_called_with(
        method="GET",
        endpoint="/test",
        status=200
    )
    counter.labels.return_value.inc.assert_called_once()
    
    hist.labels.assert_called_with(
        method="GET",
        endpoint="/test"
    )
    hist.labels.return_value.observe.assert_called_with(0.5)
    
    # Verify call_next was called
    call_next.assert_called_once_with(request)

@pytest.mark.asyncio
async def test_security_headers_middleware():
    """Test security headers middleware"""
    app = FastAPI()
    middleware = SecurityHeadersMiddleware(app)
    
    # Create request with complete scope
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
    })
    
    response = Response(content="test")
    call_next = AsyncMock(return_value=response)
    
    result = await middleware.dispatch(request, call_next)
    
    # Verify security headers
    assert result.headers["X-Frame-Options"] == "DENY"
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["X-XSS-Protection"] == "1; mode=block"
    assert result.headers["Content-Security-Policy"] == "default-src 'self'"

@pytest.mark.asyncio
async def test_timing_middleware_error_handling():
    """Test timing middleware error handling"""
    app = FastAPI()
    middleware = TimingMiddleware(app)
    
    # Create request with complete scope
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
    })
    
    # Create error-raising call_next
    async def error_next(_):
        raise ValueError("Test error")
    
    # Mock time.time() with enough values for error path
    with patch('time.time') as mock_time:
        mock_time.side_effect = [1000.0, 1000.5, 1001.0]  # start, error, cleanup
        with pytest.raises(ValueError):
            await middleware.dispatch(request, error_next)