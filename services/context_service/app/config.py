from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic import ConfigDict

class Settings(BaseSettings):
    """
    Configuration settings for Context Service
    """
    # Service information
    SERVICE_NAME: str = "context-service"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # ML Model configuration
    MODEL_NAME: str = "distilbert-base-uncased"
    MAX_SEQUENCE_LENGTH: int = 512
    BATCH_SIZE: int = 32
    
    # API Configuration
    API_PREFIX: str = "/api/v1"
    
    # Privacy settings
    PRIVACY_EPSILON: float = 0.1
    PRIVACY_DELTA: float = 1e-5
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8000

    model_config = ConfigDict(
        env_prefix="CONTEXT_",
        case_sensitive=True
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    """
    return Settings()