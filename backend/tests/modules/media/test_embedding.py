import io
import uuid
import pytest
import asyncio
from PIL import Image
from httpx import AsyncClient
from sqlalchemy import select
from app.database import async_session
from app.modules.media.models import MediaAsset, PhotoMetadata, MediaEmbedding, AssetStatus
from app.modules.media.services.embedding_service import EmbeddingService
from app.modules.media.services.qdrant_service import QdrantService
from app.modules.media.worker import process_media_task

def get_mock_image_bytes(width: int = 100, height: int = 100) -> bytes:
    """
    Constructs a mock JPEG file stream for testing model inferences.
    """
    img = Image.new("RGB", (width, height), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.mark.asyncio
async def test_embedding_generation_dimension():
    """
    Verifies that CLIP generates a float vector of exactly 512 dimensions,
    and that the returned vector coordinates are L2-normalized (magnitude = 1.0).
    """
    import os
    os.makedirs("./test_storage/originals", exist_ok=True)
    temp_path = "./test_storage/originals/temp_inference.jpg"
    
    # Write mock bytes to disk
    with open(temp_path, "wb") as f:
        f.write(get_mock_image_bytes(150, 150))
        
    try:
        # Run inference
        vector = await EmbeddingService.generate_embedding(temp_path)
        assert isinstance(vector, list)
        assert len(vector) == 512
        
        # Verify L2-normalization check (sum of squares is close to 1)
        magnitude = sum(coord * coord for coord in vector)
        assert abs(magnitude - 1.0) < 1e-3
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@pytest.mark.asyncio
async def test_qdrant_service_collection_lifecycle():
    """
    Verifies QdrantService automatic collection creation, collection checking,
    vector point upserts, payloads mapping, and vector deletions.
    """
    asset_id = uuid.uuid4()
    vector = [0.05] * 512  # Dummy 512-dimension vector
    model_name = "test-clip-vit-b-32"
    payload = {"filename": "vacation.jpg", "taken_at": 1700000000}
    
    # 1. Upsert vector (automatically triggers ensure_collection)
    QdrantService.upsert_vector(
        asset_id=asset_id,
        vector=vector,
        model_name=model_name,
        payload=payload
    )
    
    from app.qdrant_client_helper import get_qdrant_client
    client = get_qdrant_client()
    collection_name = QdrantService.get_collection_name(model_name)
    
    # Verify collection exists in memory database
    assert client.collection_exists(collection_name)
    
    # Retrieve point structure
    points = client.retrieve(collection_name, ids=[str(asset_id)])
    assert len(points) == 1
    assert points[0].id == str(asset_id)
    assert points[0].payload["filename"] == "vacation.jpg"
    
    # 2. Delete vector
    QdrantService.delete_vector(asset_id, model_name)
    
    # Verify point is removed
    points_after = client.retrieve(collection_name, ids=[str(asset_id)])
    assert len(points_after) == 0

@pytest.mark.asyncio
async def test_e2e_reprocessing_endpoint(async_client: AsyncClient):
    """
    Verifies that the /reprocess API endpoint triggers:
    1. Resets parent state to UPLOADED.
    2. Clears old thumbnail and database metadata.
    3. FastAPI BackgroundTasks kicks off processing worker asynchronously.
    4. Polling verifies that the status eventually transitions back to READY.
    """
    # 1. Upload file and run task to complete first pipeline
    image_data = get_mock_image_bytes(width=120, height=120)
    files = {"file": ("reprocess_target.jpg", image_data, "image/jpeg")}
    
    response = await async_client.post("/api/media/upload", files=files)
    assert response.status_code == 201
    asset_id = uuid.UUID(response.json()["id"])
    
    # Run background pipeline manually for initial setup
    await process_media_task(asset_id)
    
    # Verify ready status and child records exist
    async with async_session() as session:
        query = select(MediaAsset).where(MediaAsset.id == asset_id)
        result = await session.execute(query)
        asset = result.scalar_one()
        assert asset.status == AssetStatus.READY
        
        # Verify both extension rows are registered
        meta_count = len((await session.execute(select(PhotoMetadata).where(PhotoMetadata.media_asset_id == asset_id))).scalars().all())
        emb_count = len((await session.execute(select(MediaEmbedding).where(MediaEmbedding.media_asset_id == asset_id))).scalars().all())
        assert meta_count == 1
        assert emb_count == 1
        
    # 2. Call reprocess endpoint
    reprocess_res = await async_client.post(f"/api/media/{asset_id}/reprocess")
    assert reprocess_res.status_code == 202
    assert reprocess_res.json()["status"] == "UPLOADED"
    
    # 3. Poll status until background task completes re-processing
    reprocessed_success = False
    for _ in range(50):  # Maximum 5 seconds wait (50 * 100ms)
        status_check = await async_client.get(f"/api/media/{asset_id}/status")
        if status_check.json()["status"] == "READY":
            reprocessed_success = True
            break
        await asyncio.sleep(0.1)
        
    assert reprocessed_success is True
    
    # 4. Verify child database tables have re-populated successfully
    async with async_session() as session:
        meta_count = len((await session.execute(select(PhotoMetadata).where(PhotoMetadata.media_asset_id == asset_id))).scalars().all())
        emb_count = len((await session.execute(select(MediaEmbedding).where(MediaEmbedding.media_asset_id == asset_id))).scalars().all())
        assert meta_count == 1
        assert emb_count == 1
