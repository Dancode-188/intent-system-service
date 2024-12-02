import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from app.main import app
from app.service import ContextService
from app.dependencies import get_rate_limiter, get_api_dependencies

@pytest.fixture
def client(mock_rate_limiter):
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate_limiter
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides = {}

def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data
    
    # Verify timestamp is recent
    timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
    assert datetime.utcnow() - timestamp < timedelta(seconds=5)

def test_metrics_endpoint(client):
    """Test metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "requests_total" in data
    assert "requests_failed" in data
    assert "average_processing_time" in data

def test_context_api_endpoint_success(client, valid_request_data, valid_headers):
    """Test successful context analysis with valid API key"""
    response = client.post(
        "/api/v1/context",
        json=valid_request_data,
        headers=valid_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "context_id" in data
    assert "embedding" in data
    assert "confidence" in data
    assert "action_type" in data
    assert "processed_timestamp" in data
    
    # Verify data types and values
    assert isinstance(data["context_id"], str)
    assert isinstance(data["embedding"], list)
    assert len(data["embedding"]) == 768  # DistilBERT embedding size
    assert isinstance(data["confidence"], float)
    assert 0 <= data["confidence"] <= 1
    assert data["action_type"] in ["exploration", "search", "transaction", "other"]

def test_missing_api_key(client, valid_request_data):
    """Test request without API key"""
    response = client.post("/api/v1/context", json=valid_request_data)
    assert response.status_code == 403  # Forbidden
    data = response.json()
    assert "detail" in data

def test_invalid_api_key(client, valid_request_data):
    """Test request with invalid API key"""
    headers = {"X-API-Key": "invalid_key"}
    response = client.post(
        "/api/v1/context",
        json=valid_request_data,
        headers=headers
    )
    assert response.status_code == 401  # Unauthorized
    data = response.json()
    assert "detail" in data

def test_invalid_request_empty(client, valid_headers):
    """Test handling of empty request"""
    response = client.post(
        "/api/v1/context",
        json={},
        headers=valid_headers
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data

def test_invalid_request_missing_fields(client, valid_request_data, valid_headers):
    """Test handling of requests with missing required fields"""
    # Test missing user_id
    invalid_data = valid_request_data.copy()
    del invalid_data["user_id"]
    response = client.post(
        "/api/v1/context",
        json=invalid_data,
        headers=valid_headers
    )
    assert response.status_code == 422
    
    # Test missing action
    invalid_data = valid_request_data.copy()
    del invalid_data["action"]
    response = client.post(
        "/api/v1/context",
        json=invalid_data,
        headers=valid_headers
    )
    assert response.status_code == 422

def test_different_action_types(client, valid_request_data, valid_headers):
    """Test different action types and their classification"""
    actions = {
        "view_product": "exploration",
        "search_items": "search",
        "purchase_item": "transaction",
        "random_action": "other"
    }
    
    for action, expected_type in actions.items():
        test_data = valid_request_data.copy()
        test_data["action"] = action
        
        response = client.post(
            "/api/v1/context",
            json=test_data,
            headers=valid_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action_type"] == expected_type

def test_request_tracking(client, valid_request_data):
    """Test request tracking with custom request ID"""
    custom_headers = {
        "X-API-Key": "test_api_key",
        "X-Request-ID": "custom_request_id"
    }
    
    response = client.post(
        "/api/v1/context",
        json=valid_request_data,
        headers=custom_headers
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_context_analysis_error_handling(client, valid_request_data, valid_headers, settings):
    """Test error handling in context analysis endpoint"""
    # Create a mock service with failing process_context
    mock_service = ContextService(settings)
    mock_service.process_context = AsyncMock(side_effect=ValueError("Test error"))

    # Create a mock dependencies function that returns our mocked service
    async def get_mock_deps():
        return {
            "service": mock_service,
            "request_id": "test_request_id",
            "api_key": "test_api_key",
            "settings": settings
        }

    # Store original dependency and override
    original_deps = app.dependency_overrides.get(get_api_dependencies)
    app.dependency_overrides[get_api_dependencies] = get_mock_deps

    try:
        response = client.post(
            "/api/v1/context",
            json=valid_request_data,
            headers=valid_headers
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Error processing context: Test error" in data["detail"]
    finally:
        # Restore original dependency
        if original_deps:
            app.dependency_overrides[get_api_dependencies] = original_deps
        else:
            del app.dependency_overrides[get_api_dependencies]