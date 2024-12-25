from typing import Optional

class CircuitBreakerError(Exception):
    """Base circuit breaker exception."""
    pass

class CircuitOpenError(CircuitBreakerError):
    """Exception raised when circuit is open."""
    def __init__(self, service_name: str, until: Optional[str] = None):
        self.service_name = service_name
        self.until = until
        message = f"Circuit breaker is open for service {service_name}"
        if until:
            message += f" until {until}"
        super().__init__(message)

class ServiceUnavailableError(CircuitBreakerError):
    """Exception raised when service is unavailable."""
    def __init__(self, service_name: str, reason: str):
        self.service_name = service_name
        self.reason = reason
        message = f"Service {service_name} is unavailable: {reason}"
        super().__init__(message)

class CircuitConfigError(CircuitBreakerError):
    """Exception raised for configuration errors."""
    pass