import io
import uuid
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from app.database import get_db
from app.modules.media.models import MediaAsset, PhotoMetadata, MediaEmbedding, ImageQualityAssessment, AssetStatus
from app.modules.media.schemas import UploadResponse, MediaAssetResponse, StatusResponse, SearchResponse, MediaListResponse, SimilarImageResponse, QualityAssessmentResponse, BulkTrashRequest, TrashCountResponse
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
        await db.execute(delete(ImageQualityAssessment).where(ImageQualityAssessment.media_asset_id == id))
        
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

@router.post("/rebuild-ai-metadata")
async def rebuild_ai_metadata(
    db: AsyncSession = Depends(get_db)
):
    """
    HTTP POST endpoint to rebuild AI Memory Records for existing images.
    Reuses existing embeddings without regenerating vectors.
    """
    try:
        from app.modules.media.services.rebuild_ai_metadata_service import RebuildAIMetadataService
        res = await RebuildAIMetadataService.rebuild_all_metadata(db)
        return res
    except Exception as e:
        logger.error(f"Rebuild Router: Error rebuilding AI metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild AI metadata: {str(e)}"
        )

@router.get("/search", response_model=SearchResponse)
async def search_media(
    q: str = Query(..., min_length=1, description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50000, description="Maximum number of items to return"),
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


# ─── RECYCLE BIN / TRASH ENDPOINTS ──────────────────────────────────────────

@router.get("/trash/count", response_model=TrashCountResponse)
async def get_trash_count(db: AsyncSession = Depends(get_db)):
    """
    Get the total count of soft-deleted assets currently in the Recycle Bin.
    """
    from sqlalchemy import func
    stmt = select(func.count(MediaAsset.id)).where(MediaAsset.is_deleted == True)
    res = await db.execute(stmt)
    count = res.scalar() or 0
    return {"count": count}


@router.get("/trash", response_model=MediaListResponse)
async def list_trash(
    limit: int = Query(50000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all soft-deleted assets currently in the Recycle Bin.
    Automatically runs 30-day cleanup before returning items.
    Calculates remaining_days for each asset.
    """
    from sqlalchemy import func
    # Run auto-cleanup for items older than 30 days
    await DeleteService.cleanup_expired_trash(db=db, retention_days=30)

    count_stmt = select(func.count(MediaAsset.id)).where(MediaAsset.is_deleted == True)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    stmt = (
        select(MediaAsset)
        .options(
            selectinload(MediaAsset.photo_metadata),
            selectinload(MediaAsset.ai_analysis),
            selectinload(MediaAsset.quality_assessment)
        )
        .where(MediaAsset.is_deleted == True)
        .order_by(MediaAsset.deleted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    now = datetime.now(timezone.utc)
    for asset in items:
        if asset.deleted_at:
            del_at = asset.deleted_at if asset.deleted_at.tzinfo else asset.deleted_at.replace(tzinfo=timezone.utc)
            days_passed = (now - del_at).days
            asset.remaining_days = max(0, 30 - days_passed)
        else:
            asset.remaining_days = 30

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.post("/{id}/restore", status_code=status.HTTP_200_OK)
async def restore_media(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Restore a soft-deleted media asset from the Recycle Bin back to the active library.
    """
    success = await DeleteService.restore_media(db=db, asset_id=id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found or restoration failed."
        )
    return {"message": "Media asset restored successfully"}


@router.post("/trash/restore-bulk", status_code=status.HTTP_200_OK)
async def bulk_restore_trash(
    payload: BulkTrashRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk restore multiple assets from the Recycle Bin.
    """
    restored_count = 0
    for asset_id in payload.ids:
        if await DeleteService.restore_media(db=db, asset_id=asset_id):
            restored_count += 1
    return {"message": f"Successfully restored {restored_count} items.", "restored_count": restored_count}


@router.post("/trash/delete-permanent-bulk", status_code=status.HTTP_200_OK)
async def bulk_delete_permanent_trash(
    payload: BulkTrashRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk permanently delete multiple assets from the Recycle Bin.
    """
    deleted_count = 0
    for asset_id in payload.ids:
        if await DeleteService.delete_media_permanently(db=db, asset_id=asset_id):
            deleted_count += 1
    return {"message": f"Successfully permanently deleted {deleted_count} items.", "deleted_count": deleted_count}


@router.delete("/trash/empty", status_code=status.HTTP_200_OK)
async def empty_trash(db: AsyncSession = Depends(get_db)):
    """
    Permanently delete all assets in the Recycle Bin.
    """
    stmt = select(MediaAsset.id).where(MediaAsset.is_deleted == True)
    res = await db.execute(stmt)
    trash_ids = res.scalars().all()

    count = 0
    for asset_id in trash_ids:
        if await DeleteService.delete_media_permanently(db=db, asset_id=asset_id):
            count += 1

    return {"message": f"Successfully emptied Recycle Bin. Permanently deleted {count} items.", "deleted_count": count}


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
            selectinload(MediaAsset.ai_analysis),
            selectinload(MediaAsset.quality_assessment)
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

@router.get("/{id}/quality", response_model=QualityAssessmentResponse)
async def get_media_quality(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    HTTP GET endpoint to retrieve stored quality assessment metadata for a media asset.
    Reads exclusively from persistent database storage. Zero re-computation on GET.
    """
    asset_query = select(MediaAsset).where(MediaAsset.id == id)
    asset_res = await db.execute(asset_query)
    if not asset_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found."
        )

    query = select(ImageQualityAssessment).where(ImageQualityAssessment.media_asset_id == id)
    result = await db.execute(query)
    quality = result.scalar_one_or_none()

    if not quality:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality assessment record not found for this media asset."
        )
    return quality

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
    limit: int = Query(30, ge=1, le=50000, description="Limit for pagination"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated active (non-deleted) media assets from the database.
    """
    from sqlalchemy import func
    count_stmt = select(func.count(MediaAsset.id)).where(MediaAsset.is_deleted == False)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(MediaAsset)
        .options(
            selectinload(MediaAsset.photo_metadata),
            selectinload(MediaAsset.ai_analysis),
            selectinload(MediaAsset.quality_assessment)
        )
        .where(MediaAsset.is_deleted == False)
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
    permanent: bool = Query(False, description="If true, permanently delete files & vectors; else soft-delete to Recycle Bin"),
    deleted_from: Optional[str] = Query(None, description="Optional name of category or view item was deleted from"),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete endpoint:
    - By default (permanent=false): Moves photo to Recycle Bin (soft delete).
    - If permanent=true: Permanently removes DB record, disk files, and Qdrant vectors.
    """
    try:
        if permanent:
            success = await DeleteService.delete_media_permanently(db=db, asset_id=id)
        else:
            success = await DeleteService.soft_delete_media(db=db, asset_id=id, deleted_from=deleted_from)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media asset not found."
            )
        return {"message": "Media deleted successfully" if not permanent else "Media permanently deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Router: Failure during deletion of asset [{id}]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media asset."
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
    stmt = select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.is_deleted == False)
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
            selectinload(MediaAsset.ai_analysis),
            selectinload(MediaAsset.quality_assessment)
        )
        .where(MediaAsset.id.in_(candidate_ids), MediaAsset.is_deleted == False)
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


@router.post("/backfill-quality", status_code=status.HTTP_200_OK)
async def backfill_quality(db: AsyncSession = Depends(get_db)):
    """
    Backfills missing Quality Assessments for all existing media assets in the database.
    """
    from app.modules.media.services.quality_persistence_service import QualityPersistenceService

    stmt = (
        select(MediaAsset)
        .outerjoin(ImageQualityAssessment, MediaAsset.id == ImageQualityAssessment.media_asset_id)
        .where(ImageQualityAssessment.id.is_(None))
    )
    res = await db.execute(stmt)
    unprocessed = res.scalars().all()

    success_count = 0
    failed_count = 0

    for asset in unprocessed:
        try:
            record = await QualityPersistenceService.evaluate_and_persist(asset.id, db)
            if record:
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Backfill error on asset [{asset.id}]: {e}")

    return {
        "status": "completed",
        "total_unprocessed": len(unprocessed),
        "success": success_count,
        "failed": failed_count,
    }



