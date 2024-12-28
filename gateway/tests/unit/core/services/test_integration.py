import pytest
import asyncio
import logging
from unittest.mock import patch
from fastapi import FastAPI

from src.core.services.config import CORE_SERVICES
from src.core.services.registry import register_core_services
from src.discovery.registry import ServiceRegistry
from src.discovery.models import ServiceStatus
from src.routing.router import RouterManager

@pytest.mark.asyncio
async def test_service_registration():
    """Test core services registration."""
    # Create registry and router
    registry = ServiceRegistry()
    router = RouterManager(registry)
    
    try:
        # Register services
        await register_core_services(registry, router)
        
        # Verify all services are registered
        for service_name in CORE_SERVICES:
            # Verify service exists in registry
            service = await registry.get_service(service_name)
            assert service.service_name == service_name
            assert len(service.instances) == 1
            
            # Verify instance is configured correctly
            instance_id = f"{CORE_SERVICES[service_name]['host']}:{CORE_SERVICES[service_name]['port']}"
            instance = service.instances[instance_id]
            assert instance.host == CORE_SERVICES[service_name]['host']
            assert instance.port == CORE_SERVICES[service_name]['port']
            assert instance.status in [ServiceStatus.STARTING, ServiceStatus.HEALTHY]
            
            # Verify route was added and configured correctly
            route = await router.get_route(CORE_SERVICES[service_name]['path_prefix'])
            assert route is not None
            assert route.service_name == service_name
            assert route.methods == CORE_SERVICES[service_name]['methods']
            assert route.circuit_breaker == CORE_SERVICES[service_name]['circuit_breaker']
            
    finally:
        # Cleanup
        await registry.close()
        await router.close()

@pytest.mark.asyncio
async def test_service_config_validation():
    """Test service configuration validation."""
    # Test all services have required fields
    required_fields = {
        'service_name', 'path_prefix', 'methods', 'host', 'port',
        'check_endpoint', 'check_interval', 'circuit_breaker'
    }
    
    for service_name, config in CORE_SERVICES.items():
        missing_fields = required_fields - set(config.keys())
        assert not missing_fields, f"Service {service_name} missing fields: {missing_fields}"
        
        # Test path prefix format
        assert config['path_prefix'].startswith('/api/v1/'), \
            f"Service {service_name} path prefix should start with /api/v1/"
            
        # Test port is valid
        assert isinstance(config['port'], int), \
            f"Service {service_name} port should be integer"
        assert 1 <= config['port'] <= 65535, \
            f"Service {service_name} port should be between 1 and 65535"

@pytest.mark.asyncio
async def test_get_route_definition():
    """Test route definition creation."""
    from src.core.services.config import get_route_definition
    
    for service_name in CORE_SERVICES:
        # Should create route definition without error
        route = get_route_definition(service_name)
        assert route.service_name == service_name
        
    # Should raise error for unknown service
    with pytest.raises(KeyError):
        get_route_definition("unknown_service")

@pytest.mark.asyncio
async def test_service_registration_error(caplog):
    """Test service registration error handling."""
    caplog.set_level(logging.ERROR)
    
    registry = ServiceRegistry()
    router = RouterManager(registry)
    
    # Mock registry.register_service to raise an exception
    with patch('src.discovery.registry.ServiceRegistry.register_service') as mock_register:
        mock_register.side_effect = Exception("Test error")
        
        # Attempt registration
        await register_core_services(registry, router)
        
        # Verify error was logged
        assert "Failed to register" in caplog.text
        assert "Test error" in caplog.text
        
    await registry.close()
    await router.close()