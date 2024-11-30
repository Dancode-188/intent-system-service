from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    """API Gateway configuration settings."""
    
    # Application settings
    APP_NAME: str = "Intent System Gateway"
    DEBUG: bool = False
    
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_PER_SECOND: int = 10
    RATE_LIMIT_BURST: int = 20
    
    # Service URLs
    CONTEXT_SERVICE_URL: str = "http://localhost:8001"
    INTENT_SERVICE_URL: str = "http://localhost:8002"
    PREDICTION_SERVICE_URL: str = "http://localhost:8003"
    REALTIME_SERVICE_URL: str = "http://localhost:8004"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"  # Should be overridden by environment variable
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=True
    )

# Create global settings instance
settings = Settings()