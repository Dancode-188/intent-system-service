import pytest
from fastapi import HTTPException
from fastapi.security import SecurityScopes

from src.auth.security import create_access_token, MOCK_USERS_DB
from src.auth.dependencies import get_current_user, get_current_active_user
from src.auth.models import User

# Add test users
MOCK_USERS_DB.update({
    "testuser": {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "hashed_password": "hashed_testpass",
        "disabled": False,
        "scopes": ["read", "write"]
    },
    "inactiveuser": {
        "username": "inactiveuser",
        "email": "inactive@example.com",
        "full_name": "Inactive User",
        "hashed_password": "hashed_testpass",
        "disabled": True,
        "scopes": ["read"]
    }
})

@pytest.mark.asyncio
async def test_get_current_user_nonexistent():
    """Test get_current_user with nonexistent user."""
    security_scopes = SecurityScopes()
    token = create_access_token({"sub": "nonexistent_user", "scopes": ["read"]})
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(security_scopes, token)
    
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found"

@pytest.mark.asyncio
async def test_get_current_user_insufficient_scope():
    """Test get_current_user with insufficient permissions."""
    security_scopes = SecurityScopes(scopes=["admin"])
    # Make sure we use an existing user with defined scopes
    token = create_access_token({
        "sub": "testuser",
        "scopes": ["read", "write"]
    })
    
    # The user exists but doesn't have admin scope
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(security_scopes, token)
    
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not enough permissions"
    assert 'Bearer scope="admin"' in exc_info.value.headers["WWW-Authenticate"]

@pytest.mark.asyncio
async def test_get_current_active_user_inactive():
    """Test get_current_active_user with disabled user."""
    token = create_access_token({
        "sub": "inactiveuser",
        "scopes": ["read"]
    })
    
    user = await get_current_user(SecurityScopes(), token)
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(user)
    
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Inactive user"