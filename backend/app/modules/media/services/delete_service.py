import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.media.models import MediaAsset
from app.modules.media.services.storage_service import StorageService
from app.modules.media.services.qdrant_service import QdrantService
from app.config import settings
from app.logging_config import logger

class DeleteService:
    @classmethod
    async def delete_media(cls, db: AsyncSession, asset_id: uuid.UUID) -> bool:
        """
        Orchestrates deletion of a media asset:
        1. Validates existence in PostgreSQL.
        2. Deletes the database record (cascading to metadata and embedding metadata rows).
        3. Deletes the original file from storage disk.
        4. Deletes the generated thumbnail file from storage disk.
        5. Deletes the vector representation from the Qdrant collection index.
        """
        # 1. Query database for asset existence
        stmt = select(MediaAsset).where(MediaAsset.id == asset_id)
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()
        
        if not asset:
            logger.warning(f"Delete Service: Asset [{asset_id}] not found in database for deletion request.")
            return False

        original_path = asset.original_path
        thumbnail_path = asset.thumbnail_path

        # 2. Database transaction deletion
        try:
            await db.delete(asset)
            await db.commit()
            logger.info(f"Delete Service: Database transaction committed successfully for asset [{asset_id}]")
        except Exception as e:
            logger.error(f"Delete Service: Database transaction rollback occurred for asset [{asset_id}]: {e}")
            await db.rollback()
            raise

        # 3. Storage file cleanup (non-blocking file deletes)
        if original_path:
            StorageService.delete_file(original_path)
        if thumbnail_path:
            StorageService.delete_file(thumbnail_path)

        # 4. Qdrant index deletion (non-blocking call helper)
        try:
            QdrantService.delete_vector(asset_id, settings.CLIP_MODEL_NAME)
        except Exception as e:
            logger.error(f"Delete Service: Qdrant deletion cleanup error for asset [{asset_id}]: {e}")

        logger.info(f"Delete Service: Full deletion pipeline completed for asset [{asset_id}]")
        return True
