import pytest
from src.auth.security import MOCK_USERS_DB, get_password_hash

def test_mock_users_db_initial_state():
    """Test MOCK_USERS_DB initial state."""
    # Store original data
    original_db = MOCK_USERS_DB.copy()
    
    try:
        # Clear existing data to test initial state
        MOCK_USERS_DB.clear()
        
        # Import the module again to trigger initialization
        import importlib
        from src.auth import security
        importlib.reload(security)
        
        # Verify initial state
        assert isinstance(security.MOCK_USERS_DB, dict)
        assert len(security.MOCK_USERS_DB) == 0
        
    finally:
        # Restore original data
        MOCK_USERS_DB.clear()
        MOCK_USERS_DB.update(original_db)

@pytest.fixture(autouse=True)
def setup_test_users():
    """Setup and cleanup test users for each test."""
    # Store original data
    original_db = MOCK_USERS_DB.copy()
    
    # Setup test data
    test_password = get_password_hash("testpass123")
    MOCK_USERS_DB["testuser"] = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "hashed_password": test_password,
        "disabled": False
    }
    
    yield
    
    # Cleanup - restore original data
    MOCK_USERS_DB.clear()
    MOCK_USERS_DB.update(original_db)

def test_mock_users_db_modification():
    """Test MOCK_USERS_DB modification."""
    # Clear existing data
    MOCK_USERS_DB.clear()
    assert len(MOCK_USERS_DB) == 0
    
    # Add test user
    MOCK_USERS_DB["newuser"] = {
        "username": "newuser",
        "email": "new@example.com",
        "full_name": "New User",
        "hashed_password": get_password_hash("pass123"),
        "disabled": False
    }
    
    assert len(MOCK_USERS_DB) == 1
    assert "newuser" in MOCK_USERS_DB