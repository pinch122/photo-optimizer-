from datetime import datetime, timezone, timedelta
from typing import Optional, List
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
    async def soft_delete_media(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        deleted_from: Optional[str] = None
    ) -> bool:
        """
        Soft deletes a media asset by marking it as deleted and storing deletion metadata.
        Does NOT modify files, thumbnails, or Qdrant vector index.
        """
        stmt = select(MediaAsset).where(MediaAsset.id == asset_id)
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()

        if not asset:
            logger.warning(f"Delete Service: Asset [{asset_id}] not found for soft deletion.")
            return False

        try:
            asset.is_deleted = True
            asset.deleted_at = datetime.now(timezone.utc)
            asset.deleted_from = deleted_from
            await db.commit()
            logger.info(f"Delete Service: Soft deleted asset [{asset_id}] (deleted_from={deleted_from})")
            return True
        except Exception as e:
            logger.error(f"Delete Service: Failed soft deleting asset [{asset_id}]: {e}")
            await db.rollback()
            raise

    @classmethod
    async def restore_media(cls, db: AsyncSession, asset_id: uuid.UUID) -> bool:
        """
        Restores a soft-deleted media asset back to active status.
        """
        stmt = select(MediaAsset).where(MediaAsset.id == asset_id)
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()

        if not asset:
            logger.warning(f"Delete Service: Asset [{asset_id}] not found for restoration.")
            return False

        try:
            asset.is_deleted = False
            asset.deleted_at = None
            asset.deleted_from = None
            await db.commit()
            logger.info(f"Delete Service: Restored asset [{asset_id}]")
            return True
        except Exception as e:
            logger.error(f"Delete Service: Failed restoring asset [{asset_id}]: {e}")
            await db.rollback()
            raise

    @classmethod
    async def delete_media_permanently(cls, db: AsyncSession, asset_id: uuid.UUID) -> bool:
        """
        Orchestrates PERMANENT deletion of a media asset:
        1. Validates existence in PostgreSQL.
        2. Deletes the database record (cascading to metadata and embedding metadata rows).
        3. Deletes original file and thumbnail file from storage disk.
        4. Deletes vector representation from Qdrant collection index.
        """
        stmt = select(MediaAsset).where(MediaAsset.id == asset_id)
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()
        
        if not asset:
            logger.warning(f"Delete Service: Asset [{asset_id}] not found in database for permanent deletion.")
            return False

        original_path = asset.original_path
        thumbnail_path = asset.thumbnail_path

        try:
            await db.delete(asset)
            await db.commit()
            logger.info(f"Delete Service: Database record permanently deleted for asset [{asset_id}]")
        except Exception as e:
            logger.error(f"Delete Service: Rollback during permanent delete of asset [{asset_id}]: {e}")
            await db.rollback()
            raise

        if original_path:
            StorageService.delete_file(original_path)
        if thumbnail_path:
            StorageService.delete_file(thumbnail_path)

        try:
            QdrantService.delete_vector(asset_id, settings.CLIP_MODEL_NAME)
        except Exception as e:
            logger.error(f"Delete Service: Qdrant deletion error for asset [{asset_id}]: {e}")

        logger.info(f"Delete Service: Permanent deletion completed for asset [{asset_id}]")
        return True

    @classmethod
    async def delete_media(cls, db: AsyncSession, asset_id: uuid.UUID) -> bool:
        """Legacy alias — delegates to soft_delete_media."""
        return await cls.soft_delete_media(db, asset_id)

    @classmethod
    async def cleanup_expired_trash(cls, db: AsyncSession, retention_days: int = 30) -> int:
        """
        Automatically purges soft-deleted assets whose deletion timestamp is older than retention_days.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = select(MediaAsset.id).where(
            MediaAsset.is_deleted == True,
            MediaAsset.deleted_at <= cutoff
        )
        res = await db.execute(stmt)
        expired_ids = res.scalars().all()

        purged_count = 0
        for asset_id in expired_ids:
            try:
                if await cls.delete_media_permanently(db, asset_id):
                    purged_count += 1
            except Exception as e:
                logger.error(f"Delete Service: Cleanup failed for expired asset [{asset_id}]: {e}")

        if purged_count > 0:
            logger.info(f"Delete Service: Auto-cleaned up {purged_count} expired trash assets (> {retention_days} days).")
        return purged_count

