class IntentServiceException(Exception):
    """Base exception for Intent Service"""
    pass

class MLServiceError(IntentServiceException):
    """Raised when ML Service operations fail"""
    pass

class PatternError(IntentServiceException):
    """Raised when pattern operations fail"""
    pass

class DatabaseError(IntentServiceException):
    """Raised when database operations fail"""
    pass

class RateLimitError(IntentServiceException):
    """Raised when rate limits are exceeded"""
    pass