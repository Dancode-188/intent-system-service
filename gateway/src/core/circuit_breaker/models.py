from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests allowed
    OPEN = "open"         # Requests blocked, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitStats(BaseModel):
    """Circuit breaker statistics."""
    total_requests: int = 0
    failed_requests: int = 0
    successful_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class CircuitConfig(BaseModel):
    """Circuit breaker configuration."""
    failure_threshold: int = Field(
        default=5,
        description="Number of failures before opening circuit"
    )
    recovery_timeout: int = Field(
        default=60,
        description="Seconds to wait before attempting recovery"
    )
    half_open_timeout: int = Field(
        default=30,
        description="Seconds to wait in half-open state before closing"
    )
    failure_window: int = Field(
        default=120,
        description="Window in seconds to track failures"
    )
    min_throughput: int = Field(
        default=5,
        description="Minimum requests needed to consider opening circuit"
    )
    
    model_config = ConfigDict(from_attributes=True)

class CircuitContext(BaseModel):
    """Circuit execution context."""
    service_name: str
    endpoint: str
    method: str
    request_args: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)