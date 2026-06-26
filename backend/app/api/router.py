from fastapi import APIRouter
from app.database import check_db_connection
from app.qdrant_client_helper import check_qdrant_connection
from app.modules.media.router import router as media_router

router = APIRouter()

router.include_router(media_router)


@router.get("/health")
async def health_check():
    """
    Consolidated health check endpoint verifying PostgreSQL and Qdrant connectivity.
    """
    db_ok = await check_db_connection()
    qdrant_ok = await check_qdrant_connection()
    
    overall_status = "healthy" if db_ok and qdrant_ok else "unhealthy"
    
    return {
        "status": overall_status,
        "postgres": "connected" if db_ok else "disconnected",
        "qdrant": "connected" if qdrant_ok else "disconnected",
        "version": "0.1.0"
    }
