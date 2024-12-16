import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import networkx as nx
import asyncio
import uuid
from datetime import datetime

from app.service import (
    IntentService,
    IntentServiceError,
    PatternAnalysisError,
    DatabaseError
)
from app.models import PatternType
from app.config import Settings

@pytest.mark.unit
class TestIntentService:
    @pytest.fixture
    def settings(self):
        """Test settings fixture"""
        return Settings(
            NEO4J_URI="bolt://test:7687",
            NEO4J_USER="test",
            NEO4J_PASSWORD="test",
            MAX_PATTERN_DEPTH=5,
            MIN_PATTERN_CONFIDENCE=0.6
        )

    @pytest.fixture
    def mock_records(self):
        """Mock Neo4j records"""
        records = MagicMock()
        records.single = MagicMock(return_value={"result": "test"})
        return records

    @pytest.fixture
    def mock_neo4j(self, mock_records):
        """Mock Neo4j handler with pre-configured responses"""
        handler = AsyncMock()
        
        # Configure execute_query to return records
        handler.execute_query = AsyncMock()
        handler.execute_query.return_value = mock_records
        
        # Configure records() method on the result
        mock_records.records = MagicMock(return_value=[
            {"related_id": "pat_1"},
            {"related_id": "pat_2"}
        ])
        
        return handler

    @pytest.fixture
    def service(self, settings):
        """Service fixture without mocked Neo4j"""
        return IntentService(settings)

    @pytest.fixture
    def sample_intent_data(self):
        """Sample intent data for testing"""
        return {
            "action": "view_product",
            "context": {
                "product_id": "123",
                "category": "electronics"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    async def test_initialize_graph_indexes_no_handler(self, settings):
        """Test graph index initialization without handler"""
        service = IntentService(settings)
        # Should log warning but not raise error
        try:
            # Just check that no error is raised
            await asyncio.sleep(0)  # Mock async operation
            service._initialize_graph_indexes()
            assert service.neo4j is None
        except Exception as e:
            pytest.fail(f"Should not raise error: {str(e)}")

    async def test_validate_intent_data_valid(self, service, sample_intent_data):
        """Test intent data validation with valid data"""
        service._validate_intent_data(sample_intent_data)  # Should not raise error

    async def test_validate_intent_data_invalid(self, service):
        """Test intent data validation with invalid data"""
        with pytest.raises(ValueError):
            service._validate_intent_data({})  # Missing required fields
        
        with pytest.raises(ValueError):
            service._validate_intent_data({"timestamp": "2024-01-01"})  # Missing action

    async def test_analyze_intent_pattern_success(self, service, mock_neo4j, sample_intent_data):
        """Test successful intent pattern analysis"""
        # Set up the mock Neo4j handler
        service.neo4j = mock_neo4j
        mock_neo4j.execute_query.return_value = AsyncMock(
            records=MagicMock(return_value=[{"p": {"confidence": 0.8, "pattern": "test"}}])
        )
        
        result = await service.analyze_intent_pattern("user_123", sample_intent_data)
        assert result.pattern_id is not None
        assert isinstance(result.pattern_type, PatternType)
        assert result.confidence >= service.settings.MIN_PATTERN_CONFIDENCE
        assert isinstance(result.metadata, dict)

    async def test_analyze_intent_pattern_no_handler(self, service, sample_intent_data):
        """Test pattern analysis without Neo4j handler"""
        with pytest.raises(DatabaseError):
            await service.analyze_intent_pattern("user_123", sample_intent_data)

    async def test_query_patterns_success(self, service, mock_neo4j):
        """Test successful pattern query"""
        service.neo4j = mock_neo4j

        # Create mock records
        mock_data = {
            "p": {
                "id": "pat_1",
                "pattern_type": PatternType.BEHAVIORAL.value,
                "confidence": 0.8,
                "data": {"action": "test"},
                "created_at": datetime.utcnow()
            },
            "related_patterns": [
                {"id": "pat_2"},
                {"id": "pat_3"}
            ]
        }

        class MockNeo4jRecord:
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data[key]

        class MockNeo4jResult:
            def __init__(self, records):
                self._records = records

            def records(self):
                return self._records
                
            def __iter__(self):
                return iter(self._records)  # Make the result iterable
                
            def __bool__(self):
                return bool(self._records)  # Handle truthiness check

        # Create our mock record and result
        mock_record = MockNeo4jRecord(mock_data)
        mock_result = MockNeo4jResult([mock_record])

        # Mock the execute_query to return our result
        mock_neo4j.execute_query = AsyncMock(return_value=mock_result)

        # Test with default parameters
        print("\nTesting with default parameters...")
        results = await service.query_patterns("test_user")
        
        # Verify results
        assert len(results) > 0
        assert results[0]["pattern_id"] == "pat_1"
        assert results[0]["pattern_type"] == PatternType.BEHAVIORAL.value
        assert results[0]["confidence"] == 0.8
        assert isinstance(results[0]["related_patterns"], list)
        assert len(results[0]["related_patterns"]) == 2

    async def test_store_pattern_success(self, service, mock_neo4j, sample_intent_data):
        """Test successful pattern storage"""
        service.neo4j = mock_neo4j
        
        # Reset mock call count
        mock_neo4j.execute_query.reset_mock()
        
        pattern_id = "test_pattern"
        user_id = "test_user"
        patterns = {"type": "test", "data": "test_data"}

        await service._store_pattern(pattern_id, user_id, sample_intent_data, patterns)
        
        # Verify the create pattern query was called
        assert mock_neo4j.execute_query.call_count == 1
        args = mock_neo4j.execute_query.call_args[0]
        assert "CREATE (p:Pattern" in args[0]

    async def test_find_related_patterns(self, service, mock_neo4j):
        """Test finding related patterns"""
        service.neo4j = mock_neo4j
        
        # Add some nodes to the local graph
        service.graph.add_node("pat_1", action="test1")
        service.graph.add_node("pat_2", action="test2")
        service.graph.add_edge("pat_1", "pat_2")

        class MockNeo4jRecord:
            def __init__(self, data):
                self._data = data
                # Store item order for sequence access
                self._keys = list(data.keys())

            def __getitem__(self, key):
                if isinstance(key, int):
                    # Handle sequence-style access
                    data_key = self._keys[key]
                    return self._data[data_key]
                # Handle dictionary-style access
                return self._data[key]

            def __contains__(self, key):
                return key in self._data

        class MockNeo4jResult:
            def __init__(self, records):
                self._records = records

            def records(self):
                return self._records

            def __iter__(self):
                return iter(self._records)

            def __bool__(self):
                return bool(self._records)

        # Create mock records with proper structure
        mock_records = [
            MockNeo4jRecord({"related_id": "pat_3"}),
            MockNeo4jRecord({"related_id": "pat_4"})
        ]
        mock_result = MockNeo4jResult(mock_records)

        # Add debug for tracking the query
        async def debug_execute_query(query, params):
            print("\nExecuting query with params:", params)
            return mock_result

        mock_neo4j.execute_query = AsyncMock(side_effect=debug_execute_query)

        # Test finding related patterns
        print("\nCalling _find_related_patterns...")
        related = await service._find_related_patterns("pat_1", "test_user")
        print(f"Found related patterns: {related}")

        # Should include both Neo4j results and local graph neighbors
        assert len(related) == 3  # pat_2 from graph, pat_3 and pat_4 from Neo4j
        assert "pat_2" in related  # Local graph neighbor
        assert "pat_3" in related  # From Neo4j
        assert "pat_4" in related  # From Neo4j

        # Verify Neo4j was queried with correct parameters
        query_args = mock_neo4j.execute_query.call_args[0][1]
        assert query_args["pattern_id"] == "pat_1"
        assert query_args["user_id"] == "test_user"

    async def test_identify_patterns(self, service, mock_neo4j):
        """Test pattern identification"""
        service.neo4j = mock_neo4j
        
        # Create test data
        intent_data = {"action": "test_action"}
        
        # Mock Neo4j response for pattern identification
        mock_patterns = [
            {
                "p": {  # Nested under "p" to match Neo4j record structure
                    "id": str(uuid.uuid4()),
                    "confidence": 0.8,
                    "pattern_type": PatternType.BEHAVIORAL.value,
                    "data": {"action": "test_action"},
                    "created_at": datetime.utcnow()
                }
            },
            {
                "p": {
                    "id": str(uuid.uuid4()),
                    "confidence": 0.9,
                    "pattern_type": PatternType.BEHAVIORAL.value,
                    "data": {"action": "test_action"},
                    "created_at": datetime.utcnow()
                }
            }
        ]

        class MockNeo4jRecord:
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data[key]

        class MockNeo4jResult:
            def __init__(self, records):
                self._records = records

            def records(self):
                return self._records

            def __iter__(self):
                return iter(self._records)

            def __bool__(self):
                return bool(self._records)

        # Create mock records
        mock_records = [MockNeo4jRecord(pattern) for pattern in mock_patterns]
        mock_result = MockNeo4jResult(mock_records)
        
        # Mock the execute_query to return our result
        mock_neo4j.execute_query = AsyncMock(return_value=mock_result)

        # Test pattern identification
        patterns = await service._identify_patterns("pat_1", intent_data)
        
        # Verify results
        assert len(patterns) == 2
        assert all(p["confidence"] >= service.settings.MIN_PATTERN_CONFIDENCE for p in patterns)
        
        # Verify query execution
        assert mock_neo4j.execute_query.called
        call_args = mock_neo4j.execute_query.call_args[0][1]
        assert call_args["action"] == "test_action"
        assert call_args["min_confidence"] == service.settings.MIN_PATTERN_CONFIDENCE

    async def test_error_handling(self, service, mock_neo4j, sample_intent_data):
        """Test various error scenarios"""
        service.neo4j = mock_neo4j

        # Test invalid intent data first
        with pytest.raises(PatternAnalysisError) as excinfo:
            await service.analyze_intent_pattern("user_123", {})
        assert "Missing required fields" in str(excinfo.value)

        # Test database error
        mock_neo4j.execute_query.side_effect = Exception("Database error")
        with pytest.raises(PatternAnalysisError) as excinfo:
            await service.analyze_intent_pattern("user_123", sample_intent_data)
        assert "Database error" in str(excinfo.value)
        
        # Reset mock for next test
        mock_neo4j.execute_query.side_effect = None
        mock_neo4j.execute_query.reset_mock()

        # Test missing Neo4j handler
        service.neo4j = None
        with pytest.raises(DatabaseError) as excinfo:
            await service.analyze_intent_pattern("user_123", sample_intent_data)
        assert "Neo4j handler not initialized" in str(excinfo.value)

    async def test_close(self, service):
        """Test service close/cleanup"""
        service.neo4j = MagicMock()
        await service.close()
        assert service.neo4j is None  # Tests line 356

    async def test_create_constraint_error(self, service, mock_neo4j):
        """Test constraint creation error handling"""
        service.neo4j = mock_neo4j
        mock_neo4j.execute_query = AsyncMock(side_effect=Exception("Test error"))
        
        # Call the method and wait a bit to allow the task to execute
        service._initialize_graph_indexes()  # Removed await since method isn't async
        await asyncio.sleep(0.1)  # Give time for the background task to run
        
        # Verify execute_query was called with correct parameters
        mock_neo4j.execute_query.assert_called_once()
        call_args = mock_neo4j.execute_query.call_args
        assert "CREATE CONSTRAINT" in call_args[0][0]
        assert isinstance(call_args[0][1], dict)

        # Test when neo4j isn't set
        service.neo4j = None
        service._initialize_graph_indexes()  # Should log warning but not raise error

    async def test_determine_pattern_type(self, service):
        """Test pattern type determination"""
        # Test empty patterns
        assert service._determine_pattern_type([]) == PatternType.BEHAVIORAL  # Tests lines 313-314
        
        # Test existing PatternType object
        pattern_with_enum = [{"pattern_type": PatternType.BEHAVIORAL}]
        assert service._determine_pattern_type(pattern_with_enum) == PatternType.BEHAVIORAL
        
        # Test pattern type as string value
        pattern_with_value = [{"pattern_type": PatternType.BEHAVIORAL.value}]
        pattern_type = service._determine_pattern_type(pattern_with_value)
        assert pattern_type == PatternType.BEHAVIORAL  # Tests lines 320-321
        
        # Test default return when no pattern type found
        pattern_without_type = [{"some_field": "value"}]
        assert service._determine_pattern_type(pattern_without_type) == PatternType.BEHAVIORAL  # Tests line 328
        
        # Test with multiple patterns - should return most common type
        mixed_patterns = [
            {"pattern_type": PatternType.BEHAVIORAL.value},
            {"pattern_type": PatternType.BEHAVIORAL.value},
            {"pattern_type": "some_other_type"}
        ]
        assert service._determine_pattern_type(mixed_patterns) == PatternType.BEHAVIORAL

    async def test_calculate_confidence(self, service):
        """Test confidence calculation"""
        # Test empty patterns
        assert service._calculate_confidence([]) == 0.7  # Tests lines 334-335
        
        # Test patterns with confidence values
        patterns = [
            {"confidence": 0.8},
            {"confidence": 0.9}
        ]
        confidence = service._calculate_confidence(patterns)
        assert confidence == pytest.approx(0.85, rel=1e-9)  # Using approx for float comparison
        
        # Test patterns without confidence - should use default 0.7
        patterns_no_confidence = [
            {"no_confidence": True},
            {"other_field": "value"}
        ]
        assert service._calculate_confidence(patterns_no_confidence) == 0.7  # Tests line 348
        
        # Test mixed patterns
        mixed_patterns = [
            {"confidence": 0.6},  # Below minimum
            {"confidence": 0.8},
            {"no_confidence": True}  # Will use default 0.7
        ]
        confidence = service._calculate_confidence(mixed_patterns)
        assert confidence >= 0.7

    async def test_store_pattern_with_different_types(self, service, mock_neo4j):
        """Test storing patterns of different types"""
        service.neo4j = mock_neo4j
        pattern_id = "test_pattern"
        user_id = "test_user"
        intent_data = {"action": "test"}
        
        # Test string pattern
        await service._store_pattern(pattern_id, user_id, intent_data, "test_pattern")  # Tests lines 175-176
        
        # Test list pattern
        await service._store_pattern(pattern_id, user_id, intent_data, ["test1", "test2"])  # Tests lines 177-178
        
        # Test database error
        mock_neo4j.execute_query = AsyncMock(side_effect=Exception("Test error"))
        with pytest.raises(DatabaseError) as exc_info:
            await service._store_pattern(pattern_id, user_id, intent_data, "test")  # Tests lines 211-213
        assert "Failed to store pattern" in str(exc_info.value)

    async def test_empty_results_handling(self, service, mock_neo4j):
        """Test handling of empty results"""
        service.neo4j = mock_neo4j
        
        # Test empty query results
        mock_neo4j.execute_query = AsyncMock(return_value=MagicMock(records=MagicMock(return_value=[])))
        results = await service.query_patterns("test_user")
        assert results == []  # Tests lines 259-260
        
        # Test empty pattern identification
        mock_neo4j.execute_query = AsyncMock(return_value=None)
        patterns = await service._identify_patterns("pattern_id", {"action": "test"})
        assert patterns == []  # Tests lines 299-300

    async def test_find_related_patterns_error(self, service, mock_neo4j):
        """Test error handling in find_related_patterns"""
        service.neo4j = mock_neo4j
        mock_neo4j.execute_query = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(Exception) as exc_info:
            await service._find_related_patterns("pattern_id", "user_id")
        assert "Database error" in str(exc_info.value)

    async def test_query_patterns_database_error(self, service, mock_neo4j):
        """Test error handling in query_patterns when database error occurs"""
        service.neo4j = mock_neo4j
        mock_neo4j.execute_query = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(DatabaseError) as exc_info:
            await service.query_patterns("test_user")
        
        # Verify error message
        assert "Failed to query patterns" in str(exc_info.value)
        assert "Database error" in str(exc_info.value)

    async def test_query_patterns_no_results(self, service, mock_neo4j):
        """Test handling of empty results in query_patterns"""
        service.neo4j = mock_neo4j

        class EmptyResult:
            def __iter__(self):
                return iter([])
            def __bool__(self):
                return False

        # Configure mock to return empty result
        mock_neo4j.execute_query = AsyncMock(return_value=EmptyResult())

        # Test empty results
        results = await service.query_patterns("test_user")
        assert results == []  # Tests line 260

    async def test_query_patterns_no_handler(self, service):
        """Test query patterns without Neo4j handler"""
        service.neo4j = None
        with pytest.raises(DatabaseError) as exc_info:
            await service.query_patterns("test_user")
        assert "Neo4j handler not initialized" in str(exc_info.value)

    async def test_initialize_graph_indexes_failures(self, service, mock_neo4j, caplog):
        """Test handling of constraint creation error with logging"""
        import logging
        caplog.set_level(logging.WARNING)
        
        service.neo4j = mock_neo4j
        
        # Mock async create_task to execute immediately
        async def mock_execute_query(*args, **kwargs):
            raise Exception("Constraint creation failed")
        
        mock_neo4j.execute_query = AsyncMock(side_effect=mock_execute_query)
        
        # Replace asyncio.create_task with immediate execution
        original_create_task = asyncio.create_task
        def sync_create_task(coro):
            try:
                asyncio.get_event_loop().run_until_complete(coro)
            except Exception as e:
                # This should trigger the warning log
                pass
            return asyncio.create_task(asyncio.sleep(0))  # Return dummy task
        
        # Apply the patch
        with patch('asyncio.create_task', side_effect=sync_create_task):
            service._initialize_graph_indexes()
        
        # Print captured logs for debugging
        print("\nCaptured logs:")
        for record in caplog.records:
            print(f"Logger: {record.name}, Level: {record.levelname}, Message: {record.message}")
        
        assert any(
            record.levelname == "WARNING" and
            "Failed to create constraint" in record.message
            for record in caplog.records
        ), f"Expected warning message not found in logs: {[r.message for r in caplog.records]}"

    async def test_store_pattern_no_handler(self, service, sample_intent_data):
        """Test storing pattern without Neo4j handler"""
        service.neo4j = None
        pattern_id = "test_pattern"
        user_id = "test_user"
        patterns = {"data": "test"}
        
        with pytest.raises(DatabaseError) as exc_info:
            await service._store_pattern(pattern_id, user_id, sample_intent_data, patterns)
        assert "Neo4j handler not initialized" in str(exc_info.value)

    async def test_determine_pattern_type_empty_type_counts(self, service):
        """Test pattern type determination when type_counts is empty"""
        print("\nTesting determine_pattern_type with empty type_counts")
        
        # Create pattern that will bypass type_counts
        patterns = [
            {
                'pattern_type': PatternType.BEHAVIORAL.value,  # Use valid enum value
                'confidence': 0.5
            }
        ]
        
        # Print debug info
        print(f"Input patterns: {patterns}")
        try:
            result = service._determine_pattern_type(patterns)
            print(f"Result: {result}")
            assert result == PatternType.BEHAVIORAL
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            raise

    async def test_calculate_confidence_all_skipped(self, service):
        """Test confidence calculation when no valid confidences exist"""
        print("\nTesting calculate_confidence with no valid confidences")
        
        # Use a non-dict pattern so it skips the confidence calculation entirely
        patterns = [None]  # This will skip the isinstance(pattern, dict) check
        
        # Print debug info
        print(f"Input patterns: {patterns}")
        result = service._calculate_confidence(patterns)
        print(f"Result: {result}")
        assert result == 0.7  # Should hit line 348