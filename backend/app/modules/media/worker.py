import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.modules.media.models import MediaAsset, PhotoMetadata, AssetStatus
from app.modules.media.services.storage_service import StorageService
from app.modules.media.services.thumb_service import ThumbnailService
from app.modules.media.services.metadata_service import MetadataService
from app.logging_config import logger

async def process_media_task(asset_id: uuid.UUID) -> None:
    """
    Coordinates asynchronous processing for uploaded media within a single database session lifespan:
    1. Fetches the MediaAsset record by ID, verifies UPLOADED status, and transitions to PROCESSING.
    2. Spawns tasks for EXIF metadata extraction and WebP thumbnail generation using settings size.
    3. Saves generated WebP thumbnails to storage asynchronously.
    4. Populates the PhotoMetadata details table and updates MediaAsset to READY.
    If an error occurs, the session rolls back, written thumbnails are cleaned up, and status is set to FAILED.
    """
    logger.info(f"Background Worker: Initializing processing task for media asset [{asset_id}]")
    
    thumbnail_path = None
    async with async_session() as session:
        try:
            # 1. Fetch asset and transition status to PROCESSING
            query = select(MediaAsset).where(MediaAsset.id == asset_id)
            result = await session.execute(query)
            asset = result.scalar_one_or_none()
            
            if not asset:
                logger.error(f"Background Worker: Asset [{asset_id}] not found in database. Processing aborted.")
                return
                
            if asset.status != AssetStatus.UPLOADED:
                logger.warning(f"Background Worker: Asset [{asset_id}] status is '{asset.status}' (expected 'UPLOADED'). Processing aborted.")
                return

            # Update parent state to PROCESSING
            asset.status = AssetStatus.PROCESSING
            asset.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Background Worker: Asset [{asset_id}] transitioned to PROCESSING.")
            original_path = asset.original_path

            # 2. Extract EXIF properties
            logger.info(f"Background Worker: Triggering metadata extraction for [{asset_id}]")
            metadata = await MetadataService.extract_metadata(original_path)
            
            # 3. Generate WebP thumbnail bytes using configured size
            logger.info(f"Background Worker: Triggering thumbnail generation for [{asset_id}] using size {settings.THUMBNAIL_SIZE}")
            thumbnail_bytes = await ThumbnailService.generate_thumbnail(
                original_path, 
                size=settings.THUMBNAIL_SIZE
            )
            
            # 4. Save thumbnail to disk asynchronously
            thumbnail_path = await StorageService.save_thumbnail(thumbnail_bytes, asset_id)
            
            # 5. Populate metadata DB tables and mark READY
            photo_meta = PhotoMetadata(
                id=uuid.uuid4(),
                media_asset_id=asset_id,
                width=metadata["width"],
                height=metadata["height"],
                camera_make=metadata["camera_make"],
                camera_model=metadata["camera_model"],
                exposure_time=metadata["exposure_time"],
                f_number=metadata["f_number"],
                iso_speed=metadata["iso_speed"],
                gps_latitude=metadata["gps_latitude"],
                gps_longitude=metadata["gps_longitude"]
            )
            session.add(photo_meta)
            
            # Complete parent asset details
            asset.thumbnail_path = thumbnail_path
            asset.status = AssetStatus.READY
            
            # Map taken timestamp if extracted from EXIF, otherwise fall back to upload default
            if metadata["taken_at"]:
                asset.taken_at = metadata["taken_at"]
            
            asset.updated_at = datetime.now(timezone.utc)
            await session.commit()
            
            logger.info(f"Background Worker Success: Asset [{asset_id}] completed processing and is now READY.")
            
        except Exception as e:
            logger.error(f"Background Worker Exception for asset [{asset_id}]: {e}. Triggering rollback recovery.")
            await session.rollback()
            
            # Cleanup files written during failed processing to avoid clutter
            if thumbnail_path:
                StorageService.delete_file(thumbnail_path)
                
            # Set database state to FAILED
            try:
                # Reload asset state to ensure we can modify status
                query = select(MediaAsset).where(MediaAsset.id == asset_id)
                result = await session.execute(query)
                asset = result.scalar_one_or_none()
                if asset:
                    asset.status = AssetStatus.FAILED
                    asset.error_message = str(e)[:1000]
                    asset.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(f"Background Worker: Asset [{asset_id}] marked as FAILED in database.")
            except Exception as db_err:
                logger.error(f"Background Worker critical failure: Could not record FAILED state for asset [{asset_id}]: {db_err}")
