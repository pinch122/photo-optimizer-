import os
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import UUID
import anyio
from app.config import settings
from app.logging_config import logger

class StorageService:
    @staticmethod
    def get_relative_dir() -> str:
        """
        Returns a YYYY/MM partition structure to limit folder sizes.
        """
        now = datetime.now(timezone.utc)
        return f"{now.strftime('%Y')}/{now.strftime('%m')}"

    @classmethod
    async def save_original(cls, file_obj: BinaryIO, file_id: UUID) -> str:
        """
        Asynchronously saves the uploaded original file stream to storage/originals/YYYY/MM/{UUID}.original.
        Returns the absolute filepath string.
        """
        rel_dir = cls.get_relative_dir()
        dest_dir = Path(settings.STORAGE_PATH) / "originals" / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / f"{file_id}.original"
        
        # Read from file-like stream to extract content bytes asynchronously
        file_obj.seek(0)
        contents = file_obj.read()
        file_obj.seek(0)
        
        async with await anyio.open_file(dest_path, "wb") as f:
            await f.write(contents)
        
        logger.info(f"Saved original asset [{file_id}] to disk: {dest_path}")
        return str(dest_path)

    @classmethod
    async def save_thumbnail(cls, image_bytes: bytes, file_id: UUID) -> str:
        """
        Asynchronously saves the processed WebP thumbnail to storage/thumbnails/YYYY/MM/{UUID}.webp.
        Returns the absolute filepath string.
        """
        rel_dir = cls.get_relative_dir()
        dest_dir = Path(settings.STORAGE_PATH) / "thumbnails" / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / f"{file_id}.webp"
        
        async with await anyio.open_file(dest_path, "wb") as f:
            await f.write(image_bytes)
        
        logger.info(f"Saved thumbnail asset [{file_id}] to disk: {dest_path}")
        return str(dest_path)

    @staticmethod
    def delete_file(file_path: Optional[str]) -> None:
        """
        Safely removes file from disk if path is provided and exists.
        """
        if not file_path:
            return
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                os.remove(path)
                logger.info(f"Storage clean up: Removed file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file at {file_path}: {e}")
            # Raise no exception to avoid interrupting broader rollbacks
