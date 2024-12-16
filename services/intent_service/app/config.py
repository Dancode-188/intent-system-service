from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """
    Configuration settings for Intent Service
    """
    # Service information
    SERVICE_NAME: str = "intent-service"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API Configuration 
    API_PREFIX: str = "/api/v1"
    
    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"  # Should be overridden via environment variable
    NEO4J_POOL_SIZE: int = 50
    NEO4J_MAX_AGE: int = 3600  # 1 hour
    NEO4J_MAX_RETRY: int = 3
    NEO4J_RETRY_DELAY: int = 1  # seconds
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 20
    REDIS_TIMEOUT: int = 10  # seconds
    REDIS_RETRY_ATTEMPTS: int = 3
    
    # Graph Configuration
    MAX_PATTERN_DEPTH: int = 5
    MIN_PATTERN_CONFIDENCE: float = 0.6
    MAX_RELATIONSHIPS: int = 1000
    
    # Rate Limiting
    RATE_LIMIT_WINDOW: int = 60  # seconds
    MAX_REQUESTS_PER_WINDOW: int = 100
    BURST_MULTIPLIER: float = 2.0  # For burst limit calculation
    
    # Cache Configuration
    CACHE_TTL: int = 3600  # 1 hour
    CACHE_ENABLED: bool = True
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    
    model_config = ConfigDict(
        env_prefix="INTENT_",  # Using INTENT_ prefix for environment variables
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    """
    return Settings()

# Validation function for settings
def validate_settings(settings: Settings) -> None:
    """
    Validate settings and their relationships
    """
    if settings.MAX_PATTERN_DEPTH > 10:
        raise ValueError("MAX_PATTERN_DEPTH cannot exceed 10")
        
    if settings.MIN_PATTERN_CONFIDENCE < 0 or settings.MIN_PATTERN_CONFIDENCE > 1:
        raise ValueError("MIN_PATTERN_CONFIDENCE must be between 0 and 1")
        
    if settings.RATE_LIMIT_WINDOW < 1:
        raise ValueError("RATE_LIMIT_WINDOW must be positive")
        
    if settings.NEO4J_POOL_SIZE < 1:
        raise ValueError("NEO4J_POOL_SIZE must be positive")