from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, UTC
from pydantic import BaseModel, Field, ConfigDict

class ServiceStatus(str, Enum):
    """Service instance health status."""
    UNKNOWN = "unknown"    # Initial state or status unclear
    HEALTHY = "healthy"    # Passing health checks
    UNHEALTHY = "unhealthy"  # Failed health checks
    STARTING = "starting"  # New instance, not yet checked
    STOPPED = "stopped"    # Gracefully stopped
    FAILED = "failed"      # Failed unexpectedly

class ServiceInstance(BaseModel):
    """Individual service instance details."""
    instance_id: str = Field(..., description="Unique instance identifier")
    host: str = Field(..., description="Instance hostname/IP")
    port: int = Field(..., description="Instance port")
    status: ServiceStatus = Field(default=ServiceStatus.UNKNOWN)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    last_check: Optional[datetime] = Field(default=None)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(from_attributes=True)

class ServiceDefinition(BaseModel):
    """Service definition including all instances."""
    service_name: str = Field(..., description="Unique service identifier")
    instances: Dict[str, ServiceInstance] = Field(default_factory=dict)
    check_endpoint: str = Field(default="/health")
    check_interval: int = Field(default=30, description="Health check interval in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)

class RegistrationRequest(BaseModel):
    """Service registration request."""
    service_name: str
    host: str
    port: int
    check_endpoint: Optional[str] = "/health"
    check_interval: Optional[int] = 30
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)