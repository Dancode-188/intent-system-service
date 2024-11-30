import pytest
from jose import jwt
from datetime import datetime, timedelta, UTC
from fastapi import HTTPException, status

from src.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token
)
from src.config import settings

def test_password_hashing():
    """Test password hashing and verification."""
    password = "testpassword123"
    hashed = get_password_hash(password)
    
    # Verify hashed password is different from original
    assert hashed != password
    
    # Verify password verification works
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

@pytest.mark.asyncio
async def test_access_token_creation():
    """Test JWT token creation and validation."""
    # Test data
    test_data = {
        "sub": "testuser",
        "scopes": ["read", "write"]
    }
    
    # Create token
    token = create_access_token(test_data)
    
    # Decode token
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    
    # Verify payload
    assert payload["sub"] == test_data["sub"]
    assert payload["scopes"] == test_data["scopes"]
    assert "exp" in payload

@pytest.mark.asyncio
async def test_token_expiration():
    """Test token expiration."""
    # Create token that expires in 1 second
    token = create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(seconds=1)
    )
    
    # Verify token is valid
    token_data = await verify_token(token)
    assert token_data.sub == "testuser"
    
    # Wait for token to expire
    import asyncio
    await asyncio.sleep(2)
    
    # Verify token is now invalid
    with pytest.raises(Exception):
        await verify_token(token)

@pytest.mark.asyncio
async def test_invalid_token():
    """Test invalid token handling."""
    # Test with malformed token
    with pytest.raises(Exception):
        await verify_token("invalid-token")

@pytest.mark.asyncio
async def test_verify_token_no_username():
    """Test verify_token when token payload has no username."""
    # Create token without 'sub' claim
    token = jwt.encode(
        {"scopes": ["read"], "exp": datetime.now(UTC) + timedelta(minutes=15)},
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_token(token)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid authentication credentials"
    assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"