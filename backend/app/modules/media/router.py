import io
import uuid
import os
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.modules.media.models import MediaAsset
from app.modules.media.schemas import UploadResponse, MediaAssetResponse, StatusResponse
from app.modules.media.services.upload_service import UploadService, DuplicateAssetError
from app.modules.media.worker import process_media_task
from app.logging_config import logger

router = APIRouter(prefix="/media", tags=["Media"])

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    HTTP POST endpoint to upload a single image asset:
    1. Synchronously reads file bytes and checks signature/hash.
    2. Registers UPLOADED asset record in DB.
    3. Queues background worker task to extract metadata & generate thumbnails.
    """
    try:
        # Load upload stream fully into memory to enable multi-seek pointer actions (hashing & saving)
        contents = await file.read()
        file_io = io.BytesIO(contents)
        
        # Delegate synchronously to UploadService
        asset = await UploadService.process_upload(
            db=db,
            file_obj=file_io,
            filename=file.filename or "unknown_asset",
            mime_type=file.content_type or "application/octet-stream",
            file_size=len(contents)
        )
        
        # Delegate heavy processing tasks to the FastAPI background task pool
        background_tasks.add_task(process_media_task, asset.id)
        
        return asset
        
    except DuplicateAssetError as e:
        logger.info(f"Upload Router: Upload rejected. Duplicate asset conflict: {e.asset_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate file detected. This file already exists in the gallery.",
                "duplicate_id": str(e.asset_id)
            }
        )
    except HTTPException:
        # Pass through expected HTTPExceptions raised in UploadService
        raise
    except Exception as e:
        logger.error(f"Upload Router: Unexpected error during file processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred during upload ingestion pipeline."
        )

@router.get("/{id}/status", response_model=StatusResponse)
async def get_media_status(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the processing status of the media asset.
    """
    query = select(MediaAsset).where(MediaAsset.id == id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found."
        )
    return asset

@router.get("/{id}", response_model=MediaAssetResponse)
async def get_media_metadata(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns complete eager-loaded metadata (including parent core fields and child photo attributes).
    """
    query = (
        select(MediaAsset)
        .options(selectinload(MediaAsset.photo_metadata))
        .where(MediaAsset.id == id)
    )
    result = await db.execute(query)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found."
        )
    return asset

@router.get("/{id}/file")
async def serve_media_file(
    id: uuid.UUID,
    size: str = Query("original", pattern="^(original|thumbnail)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Streams binary original files or generated thumbnails from filesystem storage.
    """
    query = select(MediaAsset).where(MediaAsset.id == id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found."
        )
        
    path_to_serve = None
    if size == "thumbnail":
        if not asset.thumbnail_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thumbnail has not been generated yet or is still processing."
            )
        path_to_serve = asset.thumbnail_path
    else:
        path_to_serve = asset.original_path
        
    if not path_to_serve or not os.path.exists(path_to_serve):
        logger.error(f"File serving error: Path '{path_to_serve}' is not accessible on storage disk.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset file not found on disk storage."
        )
        
    # Determine proper mime type mappings
    response_mime = asset.mime_type if size == "original" else "image/webp"
    response_name = asset.filename if size == "original" else f"thumb_{id}.webp"
    
    return FileResponse(
        path=path_to_serve,
        media_type=response_mime,
        filename=response_name
    )
