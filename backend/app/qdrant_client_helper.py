from qdrant_client import QdrantClient
from app.config import settings
from app.logging_config import logger

def get_qdrant_client() -> QdrantClient:
    """
    Returns a configured QdrantClient.
    """
    return QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

async def check_qdrant_connection() -> bool:
    """
    Asynchronously checks Qdrant connectivity.
    """
    try:
        client = get_qdrant_client()
        # Ping Qdrant by fetching collections list
        client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant connection check failed: {e}")
        return False
