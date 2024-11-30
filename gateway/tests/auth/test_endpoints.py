import pytest
from fastapi.testclient import TestClient
from src.config import settings

@pytest.mark.asyncio
async def test_login_success(test_client: TestClient, test_user: dict):
    """Test successful login."""
    response = test_client.post(
        f"{settings.API_V1_PREFIX}/auth/token",
        data={
            "username": test_user["username"],
            "password": test_user["password"],
            "scope": "read write"
        }
    )
    
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(test_client: TestClient):
    """Test login with invalid credentials."""
    response = test_client.post(
        f"{settings.API_V1_PREFIX}/auth/token",
        data={
            "username": "wronguser",
            "password": "wrongpass",
            "scope": "read write"
        }
    )
    
    assert response.status_code == 401
    assert "access_token" not in response.json()

@pytest.mark.asyncio
async def test_read_users_me(authorized_client: TestClient, test_user: dict):
    """Test getting current user info."""
    response = authorized_client.get(f"{settings.API_V1_PREFIX}/users/me")
    
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["username"] == test_user["username"]
    assert user_data["email"] == test_user["email"]

@pytest.mark.asyncio
async def test_read_users_me_unauthorized(test_client: TestClient):
    """Test getting user info without authentication."""
    response = test_client.get(f"{settings.API_V1_PREFIX}/users/me")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_read_users_me_invalid_token(test_client: TestClient):
    """Test getting user info with invalid token."""
    test_client.headers = {"Authorization": "Bearer invalid-token"}
    response = test_client.get(f"{settings.API_V1_PREFIX}/users/me")
    assert response.status_code == 401