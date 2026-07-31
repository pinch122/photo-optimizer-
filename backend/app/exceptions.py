"""
Application Custom Exception Hierarchy.
Provides structured exceptions with HTTP status codes and user-friendly error messages.
"""

class SearchEngineError(Exception):
    """Base exception for search engine operations."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class QdrantConnectionError(SearchEngineError):
    """Raised when Qdrant vector database is unreachable or connection fails."""
    def __init__(self, message: str = "Unable to connect to Qdrant."):
        super().__init__(message=message, status_code=503)


class EmbeddingModelError(SearchEngineError):
    """Raised when CLIP embedding model fails to initialize or execute inference."""
    def __init__(self, message: str = "Embedding model failed to initialize."):
        super().__init__(message=message, status_code=503)


class InvalidSearchQueryError(SearchEngineError):
    """Raised when search query request is malformed or invalid."""
    def __init__(self, message: str = "Invalid search request."):
        super().__init__(message=message, status_code=400)
