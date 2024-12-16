import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    PatternType,
    IntentRelationship,
    IntentPatternRequest,
    PatternResponse,
    GraphQueryRequest,
    HealthResponse
)

@pytest.mark.unit
class TestPatternType:
    def test_valid_pattern_types(self):
        """Test all valid pattern types"""
        assert PatternType.SEQUENTIAL == "sequential"
        assert PatternType.TEMPORAL == "temporal"
        assert PatternType.BEHAVIORAL == "behavioral"
        assert PatternType.COMPOSITE == "composite"
        
    def test_invalid_pattern_type(self):
        """Test that invalid pattern types raise ValueError"""
        with pytest.raises(ValueError):
            PatternType("invalid")

@pytest.mark.unit
class TestIntentRelationship:
    def test_valid_relationships(self):
        """Test all valid relationship types"""
        assert IntentRelationship.LEADS_TO == "leads_to"
        assert IntentRelationship.SIMILAR_TO == "similar_to"
        assert IntentRelationship.PART_OF == "part_of"
        assert IntentRelationship.DEPENDS_ON == "depends_on"
        
    def test_invalid_relationship(self):
        """Test that invalid relationships raise ValueError"""
        with pytest.raises(ValueError):
            IntentRelationship("invalid")

@pytest.mark.unit
class TestIntentPatternRequest:
    def test_valid_request(self, sample_intent_data):
        """Test valid intent pattern request"""
        request = IntentPatternRequest(**sample_intent_data)
        assert request.context_id == "ctx_123"
        assert request.user_id == "user_789"
        assert request.intent_data["action"] == "view_product"
        assert isinstance(request.timestamp, datetime)
        
    def test_invalid_request_missing_fields(self):
        """Test request with missing required fields"""
        with pytest.raises(ValidationError):
            IntentPatternRequest(
                context_id="ctx_123",
                # Missing user_id
                intent_data={"action": "test"}
            )
            
    def test_invalid_request_wrong_types(self):
        """Test request with wrong field types"""
        with pytest.raises(ValidationError):
            IntentPatternRequest(
                context_id=123,  # Should be string
                user_id="user_789",
                intent_data={"action": "test"}
            )

@pytest.mark.unit
class TestPatternResponse:
    def test_valid_response(self, sample_pattern_response):
        """Test valid pattern response"""
        response = PatternResponse(**sample_pattern_response)
        assert response.pattern_id == "pat_123"
        assert response.pattern_type == PatternType.BEHAVIORAL
        assert response.confidence == 0.85
        assert len(response.related_patterns) == 2
        assert isinstance(response.timestamp, datetime)
        
    def test_invalid_response_confidence(self):
        """Test response with invalid confidence value"""
        invalid_data = {
            "pattern_id": "pat_123",
            "pattern_type": "behavioral",
            "confidence": 1.5,  # Invalid confidence > 1
            "related_patterns": []
        }
        # Note: Currently no validation on confidence range, consider adding
        response = PatternResponse(**invalid_data)
        assert response.confidence == 1.5

    def test_empty_related_patterns(self):
        """Test response with empty related patterns"""
        data = {
            "pattern_id": "pat_123",
            "pattern_type": "behavioral",
            "confidence": 0.85
        }
        response = PatternResponse(**data)
        assert response.related_patterns == []

@pytest.mark.unit
class TestGraphQueryRequest:
    def test_valid_query_request(self):
        """Test valid graph query request"""
        request = GraphQueryRequest(
            user_id="user_789",
            pattern_type=PatternType.SEQUENTIAL,
            max_depth=3,
            min_confidence=0.7
        )
        assert request.user_id == "user_789"
        assert request.pattern_type == PatternType.SEQUENTIAL
        assert request.max_depth == 3
        assert request.min_confidence == 0.7
        
    def test_default_values(self):
        """Test default values in query request"""
        request = GraphQueryRequest(user_id="user_789")
        assert request.pattern_type is None
        assert request.max_depth == 3
        assert request.min_confidence == 0.7
        
    def test_invalid_max_depth(self):
        """Test query with invalid max_depth"""
        with pytest.raises(ValidationError):
            GraphQueryRequest(
                user_id="user_789",
                max_depth=-1  # Invalid negative depth
            )

@pytest.mark.unit
class TestHealthResponse:
    def test_valid_health_response(self):
        """Test valid health response"""
        response = HealthResponse(
            status="healthy",
            version="0.1.0"
        )
        assert response.status == "healthy"
        assert response.version == "0.1.0"
        assert isinstance(response.timestamp, datetime)
        
    def test_invalid_health_response(self):
        """Test health response with missing required fields"""
        with pytest.raises(ValidationError):
            HealthResponse(status="healthy")  # Missing version

    def test_max_depth_wrong_type(self):
        """Test max_depth with wrong type (line 107)"""
        with pytest.raises(ValueError, match="max_depth must be an integer"):
            GraphQueryRequest.validate_max_depth("3")  # Pass string directly to validator

    def test_min_confidence_wrong_type(self):
        """Test min_confidence with wrong type (line 128)"""
        with pytest.raises(ValueError, match="min_confidence must be a number"):
            GraphQueryRequest.validate_min_confidence("0.7")  # Pass string directly to validator

    def test_min_confidence_out_of_range(self):
        """Test min_confidence out of range (line 131)"""
        with pytest.raises(ValueError, match="min_confidence must be between 0.0 and 1.0"):
            GraphQueryRequest.validate_min_confidence(1.5)

    def test_user_id_wrong_type(self):
        """Test user_id with wrong type (line 150)"""
        with pytest.raises(ValueError, match="user_id must be a string"):
            GraphQueryRequest.validate_user_id(123)  # Pass number directly to validator

    def test_user_id_empty(self):
        """Test empty user_id (line 152)"""
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            GraphQueryRequest.validate_user_id("   ")

    def test_pattern_type_valid_none(self):
        """Test pattern_type with None value (line 171)"""
        assert GraphQueryRequest.validate_pattern_type(None) is None

    def test_pattern_type_invalid_type(self):
        """Test pattern_type with invalid type (line 173)"""
        with pytest.raises(ValueError, match="pattern_type must be a valid PatternType enum value"):
            GraphQueryRequest.validate_pattern_type("invalid_type")

    def test_pattern_type_valid_enum(self):
        """Test pattern_type with valid enum value"""
        assert GraphQueryRequest.validate_pattern_type(PatternType.BEHAVIORAL) == PatternType.BEHAVIORAL