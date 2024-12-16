import networkx as nx
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid
import logging
import asyncio
from .models import PatternType, IntentRelationship, PatternResponse, GraphQueryRequest
from .config import Settings
from .db.neo4j_handler import Neo4jHandler
from .metrics import track_query_metrics, track_pattern_metrics

logger = logging.getLogger(__name__)

class IntentServiceError(Exception):
    """Base exception for Intent Service"""
    pass

class PatternAnalysisError(IntentServiceError):
    """Error during pattern analysis"""
    pass

class DatabaseError(IntentServiceError):
    """Database operation error"""
    pass

class IntentService:
    """
    Core Intent Service implementation
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.graph = nx.DiGraph()  # For in-memory pattern analysis
        self.neo4j: Optional[Neo4jHandler] = None  # Will be set via dependency injection

    def set_neo4j_handler(self, handler: Neo4jHandler) -> None:
        """
        Set Neo4j handler from connection manager
        """
        self.neo4j = handler
        self._initialize_graph_indexes()

    def _initialize_graph_indexes(self):
        """Initialize graph indexes and constraints"""
        if not self.neo4j:
            logger.warning("Cannot initialize indexes: Neo4j handler not set")
            return

        try:
            query = """
            CREATE CONSTRAINT pattern_id IF NOT EXISTS
            FOR (p:Pattern) REQUIRE p.id IS UNIQUE
            """
            asyncio.create_task(self.neo4j.execute_query(query, {}))
        except Exception as e:
            logger.warning(f"Failed to create constraint: {e}")

    async def analyze_intent_pattern(self, user_id: str, intent_data: Dict[str, Any]) -> PatternResponse:
        """
        Analyze intent data to identify patterns
        """
        if not self.neo4j:
            raise DatabaseError("Neo4j handler not initialized")

        pattern_id = f"pat_{uuid.uuid4().hex[:8]}"
        
        try:
            # Validate input data
            self._validate_intent_data(intent_data)
            
            # Add to local graph for pattern analysis
            self.graph.add_node(pattern_id, **intent_data)
            
            try:
                # Identify patterns
                patterns = await self._identify_patterns(pattern_id, intent_data)
                
                # Find related patterns
                related_patterns = await self._find_related_patterns(pattern_id, user_id)
            except Exception as e:
                # Convert any underlying database errors to PatternAnalysisError
                raise PatternAnalysisError(f"Failed to analyze pattern: {str(e)}") from e
            
            # Prepare metadata dictionary
            metadata = {
                "patterns": patterns,
                "timestamp": datetime.utcnow().isoformat(),
                "analysis_info": {
                    "pattern_count": len(patterns),
                    "source": "intent_analysis"
                }
            }
            
            return PatternResponse(
                pattern_id=pattern_id,
                pattern_type=self._determine_pattern_type(patterns),
                confidence=self._calculate_confidence(patterns),
                related_patterns=related_patterns,
                metadata=metadata,
                timestamp=datetime.utcnow()
            )
        except PatternAnalysisError:
            # Re-raise PatternAnalysisError directly
            raise
        except Exception as e:
            logger.error(f"Error analyzing intent pattern: {e}", exc_info=True)
            raise PatternAnalysisError(f"Failed to analyze intent pattern: {str(e)}")

    def _validate_intent_data(self, intent_data: Dict[str, Any]) -> None:
        """
        Validate intent data structure
        """
        required_fields = ["action"]
        missing_fields = [field for field in required_fields if field not in intent_data]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    async def query_patterns(
        self,
        user_id: str,
        pattern_type: Optional[PatternType] = None,
        max_depth: int = 3,
        min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Query patterns from the graph database
        """
        if not self.neo4j:
            raise DatabaseError("Neo4j handler not initialized")

        # Validate parameters
        max_depth = min(max_depth, self.settings.MAX_PATTERN_DEPTH)
        min_confidence = max(min_confidence, self.settings.MIN_PATTERN_CONFIDENCE)
            
        query = """
        MATCH (p:Pattern)
        WHERE p.user_id = $user_id
        AND (p.confidence >= $min_confidence)
        AND ($pattern_type IS NULL OR p.pattern_type = $pattern_type)
        WITH p, [(p)-[r:RELATED_TO*1..$max_depth]-(related) | related] as related_patterns
        RETURN p, related_patterns
        LIMIT 100
        """
        
        try:
            result = await self.neo4j.execute_query(
                query,
                {
                    "user_id": user_id,
                    "pattern_type": pattern_type.value if pattern_type else None,
                    "max_depth": max_depth,
                    "min_confidence": min_confidence
                }
            )
            
            return self._format_query_results(result)
        except Exception as e:
            logger.error(f"Error querying patterns: {e}", exc_info=True)
            raise DatabaseError(f"Failed to query patterns: {str(e)}")

    async def _store_pattern(
        self,
        pattern_id: str,
        user_id: str,
        intent_data: Dict[str, Any],
        patterns: Dict[str, Any]
    ):
        """
        Store pattern in Neo4j database with relationships
        """
        if not self.neo4j:
            raise DatabaseError("Neo4j handler not initialized")

        # Convert string patterns to dict if needed
        if isinstance(patterns, str):
            patterns = {"data": patterns}
        elif isinstance(patterns, (list, tuple)):
            patterns = {"data": list(patterns)}

        try:
            pattern_type = PatternType.BEHAVIORAL  # Default type
            confidence = 0.7  # Default confidence
            
            if isinstance(patterns, dict):
                pattern_type = self._determine_pattern_type([patterns])
                confidence = self._calculate_confidence([patterns])

            query = """
            CREATE (p:Pattern {
                id: $pattern_id,
                user_id: $user_id,
                data: $intent_data,
                patterns: $patterns,
                pattern_type: $pattern_type,
                confidence: $confidence,
                created_at: datetime()
            })
            """
            
            await self.neo4j.execute_query(
                query,
                {
                    "pattern_id": pattern_id,
                    "user_id": user_id,
                    "intent_data": intent_data,
                    "patterns": patterns,
                    "pattern_type": pattern_type.value,
                    "confidence": confidence
                }
            )
        except Exception as e:
            logger.error(f"Error storing pattern: {e}", exc_info=True)
            raise DatabaseError(f"Failed to store pattern: {str(e)}")

    async def _find_related_patterns(self, pattern_id: str, user_id: str) -> List[str]:
        """
        Find related patterns using both Neo4j and NetworkX
        """
        logger.debug(f"Finding related patterns for pattern_id={pattern_id}, user_id={user_id}")
        
        try:
            query = """
            MATCH (p:Pattern {id: $pattern_id})
            MATCH (p)-[r:RELATED_TO*1..2]-(related:Pattern)
            WHERE related.user_id = $user_id
            RETURN DISTINCT related.id as related_id
            """
            
            result = await self.neo4j.execute_query(
                query,
                {"pattern_id": pattern_id, "user_id": user_id}
            )
            
            # Get Neo4j patterns
            neo4j_patterns = []
            if result and hasattr(result, 'records'):
                neo4j_patterns = [r["related_id"] for r in result.records() if "related_id" in r]
            logger.debug(f"Neo4j patterns: {neo4j_patterns}")
            
            # Get local graph patterns
            local_patterns = []
            if pattern_id in self.graph:
                local_patterns = list(self.graph.neighbors(pattern_id))
            logger.debug(f"Local graph patterns: {local_patterns}")
            
            # Combine and deduplicate
            all_patterns = list(set(neo4j_patterns + local_patterns))
            logger.debug(f"Combined patterns: {all_patterns}")
            
            return all_patterns

        except Exception as e:
            logger.error(f"Error finding related patterns: {str(e)}")
            raise  # Re-raise to be caught by analyze_intent_pattern

    def _format_query_results(self, results: Any) -> List[Dict[str, Any]]:
        """Format Neo4j query results"""
        print(f"\nIn _format_query_results with results: {results}")
        if not results:
            return []
        
        formatted = []
        for record in results:
            pattern = record["p"]
            formatted.append({
                "pattern_id": pattern["id"],
                "pattern_type": pattern["pattern_type"],
                "confidence": pattern["confidence"],
                "data": pattern["data"],
                "created_at": pattern["created_at"],
                "related_patterns": [r["id"] for r in record["related_patterns"]]
            })
        return formatted

    @track_query_metrics("pattern_detection")
    async def _identify_patterns(self, pattern_id: str, intent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify patterns based on current intent data
        """
        try:
            # Query similar patterns using graph analysis
            query = """
            MATCH (p:Pattern)
            WHERE p.data.action = $action
            AND p.confidence >= $min_confidence
            RETURN p
            ORDER BY p.confidence DESC
            LIMIT 5
            """
            
            result = await self.neo4j.execute_query(
                query,
                {
                    "action": intent_data["action"],
                    "min_confidence": self.settings.MIN_PATTERN_CONFIDENCE
                }
            )

            if not result:
                return []

            # Convert result records to list
            return [record['p'] for record in (result.records() or [])]

        except Exception as e:
            logger.error(f"Error identifying patterns: {str(e)}")
            raise  # Re-raise to be caught by analyze_intent_pattern

    def _determine_pattern_type(self, patterns: List[Dict[str, Any]]) -> PatternType:
        """
        Determine the pattern type based on the pattern data
        """
        if not patterns:
            return PatternType.BEHAVIORAL  # Default type
        
        # Count pattern types in related patterns
        type_counts = {}
        for pattern in patterns:
            pattern_type = pattern.get('pattern_type', PatternType.BEHAVIORAL.value)
            if isinstance(pattern_type, PatternType):
                pattern_type = pattern_type.value
            type_counts[pattern_type] = type_counts.get(pattern_type, 0) + 1
        
        # Return most common pattern type, or default if none found
        if type_counts:
            most_common = max(type_counts.items(), key=lambda x: x[1])[0]
            return PatternType(most_common)
        return PatternType.BEHAVIORAL

    def _calculate_confidence(self, patterns: List[Dict[str, Any]]) -> float:
        """
        Calculate confidence score based on pattern analysis
        """
        if not patterns:
            return 0.7  # Base confidence for new patterns
        
        # Average confidence of related patterns with a minimum threshold
        confidences = []
        for pattern in patterns:
            if isinstance(pattern, dict):
                confidence = pattern.get('confidence', 0.7)
                confidences.append(float(confidence))
        
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            return max(avg_confidence, 0.7)  # Never return less than base confidence
        
        return 0.7
    
    async def close(self):
        """
        Clean up resources
        """

        # Don't close neo4j connection as it's managed by connection manger
        self.neo4j = None