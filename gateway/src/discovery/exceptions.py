class ServiceDiscoveryError(Exception):
    """Base exception for service discovery errors."""
    pass

class ServiceNotFoundError(ServiceDiscoveryError):
    """Service not found in registry."""
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"Service '{service_name}' not found in registry")

class RegistrationError(ServiceDiscoveryError):
    """Error during service registration."""
    pass

class ServiceUnavailableError(ServiceDiscoveryError):
    """No healthy instances available."""
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"No healthy instances available for service '{service_name}'")