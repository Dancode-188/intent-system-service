import pytest
from app.config import Settings, validate_settings

def test_validate_settings_valid():
    """Test validate_settings with valid settings"""
    settings = Settings(
        MAX_PATTERN_DEPTH=5,
        MIN_PATTERN_CONFIDENCE=0.5,
        RATE_LIMIT_WINDOW=60,
        NEO4J_POOL_SIZE=50
    )
    # Should not raise any exceptions
    validate_settings(settings)

def test_validate_settings_invalid_pattern_depth():
    """Test validate_settings with invalid MAX_PATTERN_DEPTH"""
    settings = Settings(MAX_PATTERN_DEPTH=11)  # > 10
    with pytest.raises(ValueError, match="MAX_PATTERN_DEPTH cannot exceed 10"):
        validate_settings(settings)

def test_validate_settings_invalid_confidence():
    """Test validate_settings with invalid MIN_PATTERN_CONFIDENCE"""
    settings = Settings(MIN_PATTERN_CONFIDENCE=1.5)  # > 1
    with pytest.raises(ValueError, match="MIN_PATTERN_CONFIDENCE must be between 0 and 1"):
        validate_settings(settings)
    
    settings = Settings(MIN_PATTERN_CONFIDENCE=-0.5)  # < 0
    with pytest.raises(ValueError, match="MIN_PATTERN_CONFIDENCE must be between 0 and 1"):
        validate_settings(settings)

def test_validate_settings_invalid_rate_limit():
    """Test validate_settings with invalid RATE_LIMIT_WINDOW"""
    settings = Settings(RATE_LIMIT_WINDOW=0)  # Must be positive
    with pytest.raises(ValueError, match="RATE_LIMIT_WINDOW must be positive"):
        validate_settings(settings)

def test_validate_settings_invalid_pool_size():
    """Test validate_settings with invalid NEO4J_POOL_SIZE"""
    settings = Settings(NEO4J_POOL_SIZE=0)  # Must be positive
    with pytest.raises(ValueError, match="NEO4J_POOL_SIZE must be positive"):
        validate_settings(settings)