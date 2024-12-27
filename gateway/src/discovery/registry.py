from typing import Dict, List, Optional, Set
from datetime import datetime, UTC, timedelta
import logging
import asyncio
from asyncio import Lock
import httpx

from .models import (
    ServiceDefinition, 
    ServiceInstance, 
    ServiceStatus,
    RegistrationRequest
)
from .exceptions import ServiceNotFoundError, RegistrationError, ServiceUnavailableError

logger = logging.getLogger(__name__)

class ServiceRegistry:
    """Registry for service discovery and health monitoring."""
    
    def __init__(self):
        self._services: Dict[str, ServiceDefinition] = {}
        self._lock = Lock()
        self._health_check_tasks: Set[asyncio.Task] = set()
        self._client = httpx.AsyncClient()
        
    async def register_service(self, request: RegistrationRequest) -> ServiceInstance:
        """Register a new service instance."""
        async with self._lock:
            # Create or get service definition
            service = self._services.get(request.service_name)
            if not service:
                service = ServiceDefinition(
                    service_name=request.service_name,
                    check_endpoint=request.check_endpoint,
                    check_interval=request.check_interval,
                    metadata=request.metadata
                )
                self._services[request.service_name] = service
            
            # Create instance
            instance = ServiceInstance(
                instance_id=f"{request.host}:{request.port}",
                host=request.host,
                port=request.port,
                status=ServiceStatus.STARTING,
                metadata=request.metadata
            )
            
            # Add to service instances
            service.instances[instance.instance_id] = instance
            
            # Start health checking
            self._start_health_checking(service.service_name, instance.instance_id)
            
            logger.info(
                f"Registered instance {instance.instance_id} "
                f"for service {request.service_name}"
            )
            return instance
            
    async def deregister_service(self, service_name: str, instance_id: str) -> None:
        """Deregister a service instance."""
        async with self._lock:
            service = self._services.get(service_name)
            if not service:
                raise ServiceNotFoundError(service_name)
                
            if instance_id in service.instances:
                instance = service.instances.pop(instance_id)
                instance.status = ServiceStatus.STOPPED
                
                # Remove service if no instances left
                if not service.instances:
                    del self._services[service_name]
                    
                logger.info(
                    f"Deregistered instance {instance_id} "
                    f"from service {service_name}"
                )
                
    async def get_service(self, service_name: str) -> ServiceDefinition:
        """Get service definition."""
        service = self._services.get(service_name)
        if not service:
            raise ServiceNotFoundError(service_name)
        return service
        
    async def get_instance(
        self, 
        service_name: str,
        healthy_only: bool = True
    ) -> ServiceInstance:
        """Get a service instance using round-robin selection."""
        service = await self.get_service(service_name)
        
        # Filter instances
        instances = [
            instance for instance in service.instances.values()
            if not healthy_only or instance.status == ServiceStatus.HEALTHY
        ]
        
        if not instances:
            raise ServiceUnavailableError(service_name)
            
        # Basic round-robin for now
        return instances[0]  # We'll improve this later
        
    def _start_health_checking(self, service_name: str, instance_id: str) -> None:
        """Start health checking for an instance."""
        task = asyncio.create_task(
            self._health_check_loop(service_name, instance_id)
        )
        self._health_check_tasks.add(task)
        task.add_done_callback(self._health_check_tasks.remove)
        
    async def _health_check_loop(self, service_name: str, instance_id: str) -> None:
        """Continuous health checking loop for an instance."""
        while True:
            try:
                service = self._services.get(service_name)
                if not service or instance_id not in service.instances:
                    break
                    
                instance = service.instances[instance_id]
                url = f"http://{instance.host}:{instance.port}{service.check_endpoint}"
                
                try:
                    async with self._client.stream('GET', url, timeout=5.0) as response:
                        if response.status_code == 200:
                            instance.status = ServiceStatus.HEALTHY
                        else:
                            instance.status = ServiceStatus.UNHEALTHY
                except Exception as e:
                    instance.status = ServiceStatus.FAILED
                    logger.warning(
                        f"Health check failed for {instance_id} ({service_name}): {str(e)}"
                    )
                
                instance.last_check = datetime.now(UTC)
                await asyncio.sleep(service.check_interval)
                
            except Exception as e:
                logger.error(
                    f"Error in health check loop for {instance_id} ({service_name}): {str(e)}"
                )
                await asyncio.sleep(5.0)  # Back off on errors
                
    async def close(self) -> None:
        """Cleanup registry resources."""
        # Cancel health check tasks
        for task in self._health_check_tasks:
            task.cancel()
            
        # Wait for tasks to complete
        if self._health_check_tasks:
            await asyncio.gather(
                *self._health_check_tasks, 
                return_exceptions=True
            )
            
        # Close HTTP client
        await self._client.aclose()