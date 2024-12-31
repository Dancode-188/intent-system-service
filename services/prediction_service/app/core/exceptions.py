class ServiceError(Exception):
    """Base exception for service-related errors"""
    pass

class ContextServiceError(ServiceError):
    """Raised when Context Service operations fail"""
    pass

class IntentServiceError(ServiceError):
    """Raised when Intent Service operations fail"""
    pass

class PredictionServiceError(ServiceError):
    """Raised when Prediction Service operations fail"""
    pass

class ModelError(Exception):
    """Raised when ML model operations fail"""
    pass

class ValidationError(Exception):
    """Raised when validation fails"""
    pass

class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass

class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass