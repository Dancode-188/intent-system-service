from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict

class RouteDefinition(BaseModel):
    """API route definition."""
    service_name: str
    path_prefix: str
    methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    strip_prefix: bool = True
    timeout: float = 30.0
    circuit_breaker: bool = True
    rate_limit: bool = True
    auth_required: bool = True
    scopes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)

class ProxyRequest(BaseModel):
    """Request details for proxying."""
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None
    
    model_config = ConfigDict(from_attributes=True)