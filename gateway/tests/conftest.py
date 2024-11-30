import sys
from pathlib import Path
import pytest
import os
from fastapi.testclient import TestClient
from typing import Generator, Dict, Any

# Enable testing mode
os.environ["TESTING"] = "true"

# Add the src directory to Python path
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from src.main import app
from src.auth.security import get_password_hash, create_access_token, MOCK_USERS_DB

@pytest.fixture(scope="function")
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for our API."""
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="function")
def test_user() -> Dict[str, Any]:
    """Create a test user."""
    user = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "scopes": ["read", "write"]
    }
    
    # Create user in mock database
    MOCK_USERS_DB[user["username"]] = {
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "disabled": False,
        "hashed_password": get_password_hash(user["password"]),
        "scopes": user["scopes"]
    }
    
    return user

@pytest.fixture(scope="function")
def test_user_token(test_user: Dict[str, Any]) -> Generator[str, None, None]:
    """Create a token for test user."""
    token = create_access_token(
        data={"sub": test_user["username"], "scopes": test_user["scopes"]}
    )
    yield token
    # Cleanup after test
    MOCK_USERS_DB.clear()

@pytest.fixture(scope="function")
def authorized_client(test_client: TestClient, test_user_token: str) -> TestClient:
    """Create an authorized test client."""
    test_client.headers = {
        **test_client.headers,
        "Authorization": f"Bearer {test_user_token}"
    }
    return test_client