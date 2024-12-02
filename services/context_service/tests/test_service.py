import pytest
from datetime import datetime
import numpy as np
from app.service import ContextService
from app.models import ContextRequest
from app.config import Settings

@pytest.fixture
def settings():
    return Settings()

@pytest.fixture
def service(settings):
    return ContextService(settings)

@pytest.fixture
def sample_request():
    return ContextRequest(
        user_id="test_user",
        action="view_product",
        context={
            "product_id": "123",
            "category": "electronics",
            "price": 999.99
        },
        timestamp=datetime.utcnow()
    )

@pytest.mark.asyncio
async def test_context_embedding_generation(service, sample_request):
    # Test embedding generation
    text = f"{sample_request.action} {service._format_context(sample_request.context)}"
    embedding = await service.generate_embedding(text)
    
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (768,)  # DistilBERT base embedding size

@pytest.mark.asyncio
async def test_context_processing(service, sample_request):
    # Test full context processing
    response = await service.process_context(sample_request)
    
    assert response.context_id.startswith("ctx_")
    assert isinstance(response.embedding, list)
    assert len(response.embedding) == 768
    assert 0 <= response.confidence <= 1
    assert response.action_type in ["exploration", "search", "transaction", "other"]
    assert isinstance(response.processed_timestamp, datetime)

def test_action_classification(service):
    # Test different action classifications
    embedding = np.random.rand(768)  # Mock embedding
    
    assert service._classify_action("view_product", embedding) == "exploration"
    assert service._classify_action("search_items", embedding) == "search"
    assert service._classify_action("purchase_item", embedding) == "transaction"
    assert service._classify_action("unknown_action", embedding) == "other"

def test_confidence_calculation(service):
    # Test confidence calculation
    embedding = np.ones(768) * 0.1  # Create test embedding
    confidence = service._calculate_confidence(embedding)
    
    assert isinstance(confidence, float)
    assert 0 <= confidence <= 1

def test_context_formatting(service):
    # Test context formatting
    context = {
        "product_id": "123",
        "category": "electronics",
        "price": 999.99
    }
    formatted = service._format_context(context)
    assert isinstance(formatted, str)
    assert "product_id:123" in formatted
    assert "category:electronics" in formatted
    assert "price:999.99" in formatted