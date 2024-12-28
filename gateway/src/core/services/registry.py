import logging
from typing import Dict, Any
from ...discovery.models import RegistrationRequest
from ...discovery.registry import ServiceRegistry
from .config import CORE_SERVICES, get_route_definition
from ...routing.router import RouterManager

logger = logging.getLogger(__name__)

async def register_core_services(
    registry: ServiceRegistry,
    router: RouterManager
) -> None:
    """Register all core services with the service registry."""
    for service_name, config in CORE_SERVICES.items():
        try:
            # Create registration request
            registration = RegistrationRequest(
                service_name=config["service_name"],
                host=config["host"],
                port=config["port"],
                check_endpoint=config["check_endpoint"],
                check_interval=config["check_interval"]
            )
            
            # Register with service registry
            instance = await registry.register_service(registration)
            logger.info(
                f"Registered {service_name} instance {instance.instance_id}"
            )
            
            # Add route definition
            route = get_route_definition(service_name)
            await router.add_route(route)
            logger.info(
                f"Added route for {service_name}: {route.path_prefix}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to register {service_name}: {str(e)}",
                exc_info=True
            )