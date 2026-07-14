import io
import uuid
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app.modules.media.models import MediaAsset, PhotoMetadata, MediaEmbedding, AssetStatus
from app.modules.media.schemas import UploadResponse, MediaAssetResponse, StatusResponse, SearchResponse, MediaListResponse, SimilarImageResponse
from app.modules.media.services.upload_service import UploadService, DuplicateAssetError
from app.modules.media.services.storage_service import StorageService
from app.modules.media.services.search_service import SearchService
from app.modules.media.services.delete_service import DeleteService
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

@router.post("/{id}/reprocess", response_model=StatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def reprocess_media(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    HTTP POST endpoint to force background reprocessing and vector re-indexing of a media asset:
    1. Fetches the MediaAsset record by ID.
    2. Clears existing child records (EXIF metadata and vector registrations) to avoid unique constraints.
    3. Resets status back to UPLOADED, cleans up old thumbnails, and queues background task execution.
    """
    query = select(MediaAsset).where(MediaAsset.id == id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found."
        )
        
    try:
        # 1. Clean up existing child extension tables
        await db.execute(delete(PhotoMetadata).where(PhotoMetadata.media_asset_id == id))
        await db.execute(delete(MediaEmbedding).where(MediaEmbedding.media_asset_id == id))
        
        # 2. Safely clean up old thumbnail file on disk
        StorageService.delete_file(asset.thumbnail_path)
        
        # 3. Reset parent model columns to ingest state
        asset.status = AssetStatus.UPLOADED
        asset.thumbnail_path = None
        asset.error_message = None
        asset.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(asset)
        
        # 4. Enqueue background processing pipeline again
        background_tasks.add_task(process_media_task, asset.id)
        
        return asset
        
    except Exception as e:
        logger.error(f"Reprocess Router: Error resetting assets pipeline for [{id}]: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger background re-processing execution."
        )

@router.get("/search", response_model=SearchResponse)
async def search_media(
    q: str = Query(..., min_length=1, description="Natural language search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search gallery using natural language semantic text queries.
    """
    try:
        results = await SearchService.search_media(
            db=db,
            query_text=q,
            limit=limit,
            offset=offset
        )
        return results
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Search Router: Query search failure for q='{q}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred during query evaluation."
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
        .options(
            selectinload(MediaAsset.photo_metadata),
            selectinload(MediaAsset.ai_analysis)
        )
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

@router.get("", response_model=MediaListResponse)
async def list_media(
    limit: int = Query(30, ge=1, le=100, description="Limit for pagination"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated media assets from the database.
    """
    from sqlalchemy import func
    # Count total assets
    count_stmt = select(func.count(MediaAsset.id))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Retrieve assets with metadata
    stmt = (
        select(MediaAsset)
        .options(
            selectinload(MediaAsset.photo_metadata),
            selectinload(MediaAsset.ai_analysis)
        )
        .order_by(MediaAsset.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_media(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    HTTP DELETE endpoint to remove a media asset, its files on disk, and Qdrant embeddings.
    """
    try:
        success = await DeleteService.delete_media(db=db, asset_id=id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media asset not found."
            )
        return {"message": "Media deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Router: Unexpected failure during deletion of asset [{id}]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media asset from backend repository."
        )


@router.get("/{media_id}/similar", response_model=List[SimilarImageResponse])
async def find_similar_images(
    media_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve similar images based on an existing media ID vector in Qdrant.
    Excludes the source image and filters out similarities below 80%.
    """
    from app.qdrant_client_helper import get_qdrant_client
    from app.config import settings
    from app.modules.media.services.qdrant_service import QdrantService

    # 1. Check if media asset exists in PostgreSQL first
    stmt = select(MediaAsset).where(MediaAsset.id == media_id)
    result = await db.execute(stmt)
    source_asset = result.scalar_one_or_none()
    if not source_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source media asset not found."
        )

    # 2. Retrieve vector from Qdrant
    client = get_qdrant_client()
    collection_name = QdrantService.get_collection_name(settings.CLIP_MODEL_NAME)
    try:
        points = client.retrieve(
            collection_name=collection_name,
            ids=[str(media_id)],
            with_vectors=True
        )
        if not points or not points[0].vector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Embedding for the specified media asset does not exist in Qdrant."
            )
        vector = points[0].vector
    except Exception as e:
        logger.error(f"Similar Router: Failed to retrieve vector for asset [{media_id}]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vector embedding from Qdrant."
        )

    # 3. Query Qdrant for similar vectors (limit + 1 to account for the source asset)
    try:
        candidates = QdrantService.search_vectors(
            vector=vector,
            model_name=settings.CLIP_MODEL_NAME,
            limit=limit + 1,
            offset=0
        )
    except Exception as e:
        logger.error(f"Similar Router: Qdrant search failed for asset [{media_id}]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vector search similarity lookup failed."
        )

    # 4. Filter and slice candidates
    # Exclude source_id and check similarity score >= 0.8
    valid_candidates = []
    for c in candidates:
        if c["id"] != media_id and c["score"] >= 0.8:
            valid_candidates.append(c)
            
    valid_candidates = valid_candidates[:limit]
    
    if not valid_candidates:
        return []

    # 5. Hydrate candidates from PostgreSQL
    candidate_ids = [c["id"] for c in valid_candidates]
    score_map = {c["id"]: c["score"] for c in valid_candidates}
    
    hydrate_stmt = (
        select(MediaAsset)
        .options(
            selectinload(MediaAsset.photo_metadata),
            selectinload(MediaAsset.ai_analysis)
        )
        .where(MediaAsset.id.in_(candidate_ids))
    )
    hydrated_result = await db.execute(hydrate_stmt)
    hydrated_assets = hydrated_result.scalars().all()
    assets_map = {asset.id: asset for asset in hydrated_assets}
    
    # 6. Construct response matching SimilarImageResponse
    response_items = []
    for c_id in candidate_ids:
        asset = assets_map.get(c_id)
        if asset:
            score = score_map[c_id]
            response_items.append({
                "id": asset.id,
                "filename": asset.filename,
                "thumbnail_url": f"/api/media/{asset.id}/file?size=thumbnail",
                "original_url": f"/api/media/{asset.id}/file?size=original",
                "similarity_score": score,
                "similarity_percentage": score * 100
            })
            
    return response_items


