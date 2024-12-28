import pytest
import pytest_asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
import httpx

from src.routing.models import RouteDefinition, ProxyRequest
from src.routing.router import RouterManager
from src.discovery.registry import ServiceRegistry
from src.discovery.models import ServiceInstance, ServiceStatus, RegistrationRequest
from src.core.circuit_breaker.exceptions import CircuitOpenError
from src.core.circuit_breaker.models import CircuitState

@pytest_asyncio.fixture
async def registry():
    """Create test service registry."""
    reg = ServiceRegistry()
    yield reg
    await reg.close()

@pytest_asyncio.fixture
async def router(registry):
    router_manager = RouterManager(registry)
    yield router_manager
    await router_manager.close()

@pytest.fixture
def route_definition():
    """Create test route definition."""
    return RouteDefinition(
        service_name="test_service",
        path_prefix="/test",
        methods=["GET", "POST"],
        strip_prefix=True,
        circuit_breaker=True
    )

@pytest.mark.asyncio
async def test_add_route(router, route_definition):
    """Test adding a route."""
    await router.add_route(route_definition)
    assert route_definition.path_prefix in router.routes
    assert route_definition.service_name in router.circuit_breakers

@pytest.mark.asyncio
async def test_remove_route(router, route_definition):
    """Test removing a route."""
    await router.add_route(route_definition)
    await router.remove_route(route_definition.path_prefix)
    assert route_definition.path_prefix not in router.routes
    assert route_definition.service_name not in router.circuit_breakers

@pytest.mark.asyncio
async def test_get_route(router, route_definition):
    """Test finding route for path."""
    await router.add_route(route_definition)
    route = await router.get_route("/test/api")
    assert route == route_definition
    
    route = await router.get_route("/unknown")
    assert route is None

@pytest.mark.asyncio
async def test_proxy_request_success(router, route_definition, registry):
    """Test successful request proxying."""
    # Register service first using RegistrationRequest
    registration = RegistrationRequest(
        service_name="test_service",
        host="localhost",
        port=8000,
        check_endpoint="/health",
        check_interval=1
    )
    await registry.register_service(registration)
    
    # Now we can get the service and modify its instance
    service = await registry.get_service("test_service")
    instance = service.instances[f"localhost:8000"]
    instance.status = ServiceStatus.HEALTHY
    
    await router.add_route(route_definition)
    
    # Mock request
    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.url.path = "/test/api"
    mock_request.headers = {}
    mock_request.query_params = {}
    
    # Mock response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.content = b"Success"
    mock_response.headers = {}
    mock_response.aclose = AsyncMock()  # Add this
    
    with patch('httpx.AsyncClient.request', return_value=mock_response):
        response = await router.proxy_request(mock_request, route_definition)
        
    assert response.status_code == 200
    assert response.body == b"Success"

@pytest.mark.asyncio
async def test_proxy_request_circuit_breaker(router, route_definition, registry):
    """Test circuit breaker integration in proxy."""
    # Register service first
    registration = RegistrationRequest(
        service_name="test_service",
        host="localhost",
        port=8000,
        check_endpoint="/health",
        check_interval=1
    )
    await registry.register_service(registration)

    # Get service and modify instance
    service = await registry.get_service("test_service")
    instance = service.instances[f"localhost:8000"]
    instance.status = ServiceStatus.HEALTHY

    await router.add_route(route_definition)

    # Mock request
    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.url.path = "/test/api"
    mock_request.headers = {}
    mock_request.query_params = {}

    # Configure circuit breaker for testing
    breaker = router.circuit_breakers[route_definition.service_name]
    # Use shorter window for testing
    breaker.config.failure_window = 1
    breaker.config.failure_threshold = 3  # Fewer failures needed to open

    with patch('httpx.AsyncClient.request', side_effect=Exception("Service error")):
        # Trigger failures quickly to stay within window
        for _ in range(breaker.config.failure_threshold):
            with pytest.raises(HTTPException) as exc_info:
                await router.proxy_request(mock_request, route_definition)
            assert exc_info.value.status_code == 503

        # After threshold failures, circuit should be open
        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.failed_requests == breaker.config.failure_threshold

        # Next request should fail with circuit open error
        with pytest.raises(HTTPException) as exc_info:
            await router.proxy_request(mock_request, route_definition)
        assert exc_info.value.status_code == 503
        assert "Circuit breaker is open" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_proxy_request_with_body(router, route_definition, registry):
    """Test proxying request with body content."""
    # Register service first
    registration = RegistrationRequest(
        service_name="test_service",
        host="localhost",
        port=8000,
        check_endpoint="/health",
        check_interval=1
    )
    await registry.register_service(registration)
    
    # Get service and modify instance
    service = await registry.get_service("test_service")
    instance = service.instances[f"localhost:8000"]
    instance.status = ServiceStatus.HEALTHY
    
    await router.add_route(route_definition)
    
    # Mock request with body
    mock_request = AsyncMock()
    mock_request.method = "POST"  # Using POST to trigger body reading
    mock_request.url.path = "/test/api"
    mock_request.headers = {}
    mock_request.query_params = {}
    mock_request.body.return_value = b'{"test": "data"}'
    
    # Mock response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.content = b"Success"
    mock_response.headers = {}
    mock_response.aclose = AsyncMock()
    
    with patch('httpx.AsyncClient.request', return_value=mock_response):
        response = await router.proxy_request(mock_request, route_definition)
        
    assert response.status_code == 200
    assert response.body == b"Success"

@pytest.mark.asyncio
async def test_proxy_request_without_circuit_breaker(router, registry):
    """Test proxying request without circuit breaker."""
    # Create route without circuit breaker
    route = RouteDefinition(
        service_name="test_service",
        path_prefix="/test",
        methods=["GET"],
        circuit_breaker=False  # Disable circuit breaker
    )
    
    # Register service
    registration = RegistrationRequest(
        service_name="test_service",
        host="localhost",
        port=8000,
        check_endpoint="/health",
        check_interval=1
    )
    await registry.register_service(registration)
    
    # Get service and modify instance
    service = await registry.get_service("test_service")
    instance = service.instances[f"localhost:8000"]
    instance.status = ServiceStatus.HEALTHY
    
    await router.add_route(route)
    
    # Mock request
    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.url.path = "/test/api"
    mock_request.headers = {}
    mock_request.query_params = {}
    
    # Mock response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.content = b"Success"
    mock_response.headers = {}
    mock_response.aclose = AsyncMock()
    
    with patch('httpx.AsyncClient.request', return_value=mock_response):
        response = await router.proxy_request(mock_request, route)
        
    assert response.status_code == 200
    assert response.body == b"Success"