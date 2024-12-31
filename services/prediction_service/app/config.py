from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """
    Configuration settings for Prediction Service
    """
    # Service information
    SERVICE_NAME: str = "prediction-service"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API Configuration
    API_PREFIX: str = "/api/v1"
    
    # ML Model Configuration
    MODEL_PATH: str = "models"
    CONFIDENCE_THRESHOLD: float = 0.7
    MAX_PREDICTIONS: int = 10

    # Service URLs
    CONTEXT_SERVICE_URL: str = "http://context-service:8000"
    INTENT_SERVICE_URL: str = "http://intent-service:8000"
    
    # Database Configuration
    TIMESCALE_URL: str = "postgresql://prediction_user:prediction_pass@localhost:5432/prediction_db"
    TIMESCALE_POOL_SIZE: int = 20
    
    # Redis Configuration 
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 20
    
    # Rate Limiting
    RATE_LIMIT_WINDOW: int = 60  # seconds
    MAX_REQUESTS_PER_WINDOW: int = 100
    BURST_MULTIPLIER: float = 2.0
    
    # Privacy settings
    PRIVACY_EPSILON: float = 0.1
    PRIVACY_DELTA: float = 1e-5

    model_config = ConfigDict(
        env_prefix="PREDICTION_",
        case_sensitive=True
    )

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()