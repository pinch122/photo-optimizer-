import uuid
from datetime import datetime, timezone
from typing import BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.modules.media.models import MediaAsset, MediaType, AssetStatus
from app.modules.media.services.hashing_service import HashingService
from app.modules.media.services.storage_service import StorageService
from app.logging_config import logger

class DuplicateAssetError(Exception):
    """
    Custom exception raised when an uploaded asset's SHA-256 hash already exists in PostgreSQL.
    Stores the conflicting duplicate asset UUID for downstream notifications/links.
    """
    def __init__(self, asset_id: uuid.UUID):
        self.asset_id = asset_id
        super().__init__(f"Duplicate asset detected: Conflicting record exists at UUID {asset_id}")

class UploadService:
    @staticmethod
    def validate_image_signature(file_obj: BinaryIO) -> bool:
        """
        Validates file signature magic bytes to guarantee the upload is actually an image (JPEG, PNG, WebP).
        Prevents extension-spoofing security concerns.
        """
        file_obj.seek(0)
        header = file_obj.read(12)
        file_obj.seek(0)
        
        if len(header) < 4:
            return False
        
        # JPEG signature check: FF D8 FF
        if header.startswith(b'\xff\xd8\xff'):
            return True
        # PNG signature check: 89 50 4E 47
        if header.startswith(b'\x89PNG'):
            return True
        # WebP signature check: RIFFxxxxWEBP
        if len(header) >= 12 and header.startswith(b'RIFF') and header[8:12] == b'WEBP':
            return True
            
        return False

    @classmethod
    async def process_upload(
        cls,
        db: AsyncSession,
        file_obj: BinaryIO,
        filename: str,
        mime_type: str,
        file_size: int
    ) -> MediaAsset:
        """
        Orchestrates the synchronous upload validation and storage gate:
        1. Validates magic bytes signature.
        2. Calculates the SHA-256 checksum and queries PostgreSQL for duplicates.
        3. Generates UUID and persists the raw upload stream using StorageService.
        4. Writes an database entry with status 'UPLOADED'.
        If any database write fails, the written file is automatically removed.
        """
        # 1. Mime-type signature validation
        if not cls.validate_image_signature(file_obj):
            logger.warning(f"Rejected upload of {filename}. Magic bytes signature verification failed.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported or corrupted file format. Signature check failed."
            )

        # 2. SHA-256 duplicate detection
        file_hash = HashingService.calculate_sha256(file_obj)
        
        # Check DB for duplicate SHA-256
        query = select(MediaAsset).where(MediaAsset.file_hash == file_hash)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"Duplicate upload attempt blocked. Hash match found for UUID: {existing.id}")
            raise DuplicateAssetError(asset_id=existing.id)

        # 3. Generate UUID and determine destination
        asset_id = uuid.uuid4()
        
        # 4. Save file to storage
        original_path = ""
        try:
            original_path = await StorageService.save_original(file_obj, asset_id)
        except Exception as e:
            logger.error(f"Failed writing upload stream to disk for asset [{asset_id}]: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist upload asset to storage disk."
            )

        # 5. Insert database record (status: UPLOADED)
        try:
            media_asset = MediaAsset(
                id=asset_id,
                filename=filename,
                mime_type=mime_type,
                media_type=MediaType.PHOTO, # Default to photo for MVP
                file_size=file_size,
                file_hash=file_hash,
                status=AssetStatus.UPLOADED,
                original_path=original_path,
                taken_at=datetime.now(timezone.utc) # Updated to EXIF taken_at date asynchronously
            )
            db.add(media_asset)
            await db.commit()
            await db.refresh(media_asset)
            logger.info(f"Synchronous ingest complete. Asset [{asset_id}] registered as UPLOADED.")
            return media_asset
            
        except Exception as e:
            logger.error(f"Database commit failed for upload asset [{asset_id}]: {e}. Rolling back filesystem actions.")
            await db.rollback()
            # Clean up written original file to prevent disk leaks
            StorageService.delete_file(original_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database transaction error during metadata record registration."
            )
