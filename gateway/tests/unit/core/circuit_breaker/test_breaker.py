import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, patch

from src.core.circuit_breaker.breaker import CircuitBreaker
from src.core.circuit_breaker.models import CircuitState, CircuitConfig, CircuitContext
from src.core.circuit_breaker.exceptions import CircuitOpenError, ServiceUnavailableError

@pytest.fixture
def config():
    """Create test circuit breaker config."""
    return CircuitConfig(
        failure_threshold=3,
        recovery_timeout=5,
        half_open_timeout=2,
        failure_window=60,
        min_throughput=2
    )

@pytest.fixture
def context():
    """Create test execution context."""
    return CircuitContext(
        service_name="test_service",
        endpoint="/test",
        method="GET"
    )

@pytest.fixture
def breaker(config):
    """Create test circuit breaker."""
    return CircuitBreaker("test_service", config)

@pytest.mark.asyncio
async def test_successful_execution(breaker, context):
    """Test successful service call."""
    mock_func = AsyncMock(return_value="success")
    
    result = await breaker(mock_func, context)
    
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats.successful_requests == 1
    assert breaker.stats.failed_requests == 0
    
@pytest.mark.asyncio
async def test_circuit_opens_after_failures(breaker, context):
    """Test circuit opens after threshold failures."""
    mock_func = AsyncMock(side_effect=Exception("Service error"))
    
    # Generate failures
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_func, context)
    
    assert breaker.state == CircuitState.OPEN
    assert breaker.stats.failed_requests == breaker.config.failure_threshold
    
    # Next call should fail fast
    with pytest.raises(CircuitOpenError):
        await breaker(mock_func, context)
        
@pytest.mark.asyncio
async def test_half_open_recovery(breaker, context):
    """Test circuit recovery through half-open state."""
    # Set up initial failed state
    mock_fail = AsyncMock(side_effect=Exception("Service error"))
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_fail, context)
    
    assert breaker.state == CircuitState.OPEN
    
    # Move time forward past recovery timeout
    breaker.last_state_change = datetime.now(UTC) - timedelta(
        seconds=breaker.config.recovery_timeout + 1
    )
    
    # Successful recovery
    mock_success = AsyncMock(return_value="success")
    
    # First call should move to half-open
    result = await breaker(mock_success, context)
    assert result == "success"
    assert breaker.state == CircuitState.HALF_OPEN
    
    # Enough successful calls should close circuit
    for _ in range(breaker.config.min_throughput - 1):
        result = await breaker(mock_success, context)
        assert result == "success"
    
    assert breaker.state == CircuitState.CLOSED
    
@pytest.mark.asyncio
async def test_failed_recovery(breaker, context):
    """Test failed recovery attempt."""
    # Set up initial failed state
    mock_fail = AsyncMock(side_effect=Exception("Service error"))
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_fail, context)
            
    assert breaker.state == CircuitState.OPEN
    
    # Move time forward past recovery timeout
    breaker.last_state_change = datetime.now(UTC) - timedelta(
        seconds=breaker.config.recovery_timeout + 1
    )
    
    # Failed recovery attempt
    with pytest.raises(ServiceUnavailableError):
        await breaker(mock_fail, context)
    
    assert breaker.state == CircuitState.OPEN
    
@pytest.mark.asyncio
async def test_half_open_recovery_and_limits(breaker, context):
    """Test circuit recovery behavior in half-open state."""
    # Get to OPEN state first
    mock_fail = AsyncMock(side_effect=Exception("Service error"))
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_fail, context)
    
    assert breaker.state == CircuitState.OPEN
    
    # Move to HALF_OPEN
    breaker.last_state_change = datetime.now(UTC) - timedelta(
        seconds=breaker.config.recovery_timeout + 1
    )
    
    # Test successful recovery
    mock_success = AsyncMock(return_value="success")
    
    # First success should keep in HALF_OPEN
    result = await breaker(mock_success, context)
    assert result == "success"
    assert breaker.state == CircuitState.HALF_OPEN
    
    # Complete recovery with consecutive successes
    for _ in range(breaker.config.min_throughput - 1):
        result = await breaker(mock_success, context)
        assert result == "success"
    
    # Should now be CLOSED
    assert breaker.state == CircuitState.CLOSED
    
@pytest.mark.asyncio
async def test_half_open_failure_recovery(breaker, context):
    """Test failure handling in half-open state."""
    # Get to HALF_OPEN state
    mock_fail = AsyncMock(side_effect=Exception("Service error"))
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_fail, context)
    
    breaker.last_state_change = datetime.now(UTC) - timedelta(
        seconds=breaker.config.recovery_timeout + 1
    )
    
    # One success to confirm HALF_OPEN
    mock_success = AsyncMock(return_value="success")
    result = await breaker(mock_success, context)
    assert breaker.state == CircuitState.HALF_OPEN
    
    # Failure should immediately OPEN
    mock_fail = AsyncMock(side_effect=Exception("New error"))
    with pytest.raises(ServiceUnavailableError):
        await breaker(mock_fail, context)
    assert breaker.state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_recent_failures_without_last_failure(breaker, context):
    """Test getting recent failures when no failures have occurred."""
    failures = await breaker._get_recent_failures()
    assert failures == 0

@pytest.mark.asyncio
async def test_recent_failures_outside_window(breaker, context):
    """Test getting recent failures when failures are outside the window."""
    # Set last failure time outside window
    breaker.stats.last_failure_time = datetime.now(UTC) - timedelta(
        seconds=breaker.config.failure_window + 10
    )
    breaker.stats.failed_requests = 5
    
    failures = await breaker._get_recent_failures()
    assert failures == 0

@pytest.mark.asyncio
async def test_circuit_open_error_with_name(breaker, context):
    """Test CircuitOpenError includes service name."""
    # Force circuit open
    mock_func = AsyncMock(side_effect=Exception("Service error"))
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_func, context)
            
    # Next call should raise CircuitOpenError
    with pytest.raises(CircuitOpenError) as exc_info:
        await breaker(mock_func, context)
    assert breaker.name in str(exc_info.value)

@pytest.mark.asyncio
async def test_half_open_exceed_attempts_coverage(breaker, context):
    """Force circuit to half-open with attempt count at threshold, then verify CircuitOpenError."""
    # Manually half-open
    breaker.state = CircuitState.HALF_OPEN
    breaker._half_open_count = breaker.config.min_throughput
    mock_func = AsyncMock(return_value="don't care")

    with pytest.raises(CircuitOpenError):
        # Next call should fail with CircuitOpenError
        await breaker(mock_func, context)

@pytest.mark.asyncio
async def test_reset(breaker, context):
    """Test circuit breaker reset."""
    # Set up failed state
    mock_fail = AsyncMock(side_effect=Exception("Service error"))
    for _ in range(breaker.config.failure_threshold):
        with pytest.raises(ServiceUnavailableError):
            await breaker(mock_fail, context)
            
    assert breaker.state == CircuitState.OPEN
    
    # Reset circuit
    await breaker.reset()
    
    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats.failed_requests == 0
    assert breaker.stats.successful_requests == 0
    
    # Should allow new requests
    mock_success = AsyncMock(return_value="success")
    result = await breaker(mock_success, context)
    assert result == "success"