import io
import uuid
import pytest
from PIL import Image
from httpx import AsyncClient
from sqlalchemy import select
from app.database import async_session
from app.modules.media.models import MediaAsset, PhotoMetadata, AssetStatus
from app.modules.media.services.upload_service import UploadService
from app.modules.media.services.hashing_service import HashingService
from app.modules.media.worker import process_media_task

def get_mock_image_bytes(width: int = 100, height: int = 100) -> bytes:
    """
    Dynamically constructs a valid 1x1 or custom dimensions JPEG to avoid static asset dependencies.
    """
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.mark.asyncio
async def test_image_signature_validation():
    # Valid signatures
    jpeg_bytes = get_mock_image_bytes()
    assert UploadService.validate_image_signature(io.BytesIO(jpeg_bytes)) is True
    
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...'
    assert UploadService.validate_image_signature(io.BytesIO(png_bytes)) is True
    
    webp_bytes = b'RIFF\x00\x00\x00\x00WEBPvp8 '
    assert UploadService.validate_image_signature(io.BytesIO(webp_bytes)) is True
    
    # Invalid signatures
    txt_bytes = b'Hello world image format representation'
    assert UploadService.validate_image_signature(io.BytesIO(txt_bytes)) is False

@pytest.mark.asyncio
async def test_e2e_upload_and_processing_pipeline(async_client: AsyncClient):
    # 1. POST /api/media/upload
    image_data = get_mock_image_bytes(width=200, height=150)
    files = {"file": ("test_photo.jpg", image_data, "image/jpeg")}
    
    response = await async_client.post("/api/media/upload", files=files)
    assert response.status_code == 201
    
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test_photo.jpg"
    assert data["status"] == "UPLOADED"
    asset_id = uuid.UUID(data["id"])
    
    # 2. Run the asynchronous processing worker task synchronously for testing
    await process_media_task(asset_id)
    
    # 3. GET /api/media/{id}/status
    status_response = await async_client.get(f"/api/media/{asset_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "READY"
    
    # 4. GET /api/media/{id} to verify metadata
    metadata_response = await async_client.get(f"/api/media/{asset_id}")
    assert metadata_response.status_code == 200
    meta_data = metadata_response.json()
    assert meta_data["status"] == "READY"
    assert meta_data["photo_metadata"] is not None
    assert meta_data["photo_metadata"]["width"] == 200
    assert meta_data["photo_metadata"]["height"] == 150
    
    # 5. GET /api/media/{id}/file (Original)
    file_response = await async_client.get(f"/api/media/{asset_id}/file?size=original")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "image/jpeg"
    assert len(file_response.content) == len(image_data)
    
    # 6. GET /api/media/{id}/file (Thumbnail)
    thumb_response = await async_client.get(f"/api/media/{asset_id}/file?size=thumbnail")
    assert thumb_response.status_code == 200
    assert thumb_response.headers["content-type"] == "image/webp"

@pytest.mark.asyncio
async def test_duplicate_upload_conflict(async_client: AsyncClient):
    image_data = get_mock_image_bytes(width=50, height=50)
    files = {"file": ("first_upload.jpg", image_data, "image/jpeg")}
    
    # First Upload
    res1 = await async_client.post("/api/media/upload", files=files)
    assert res1.status_code == 201
    
    # Duplicate Upload (Same contents)
    files_dup = {"file": ("second_upload.jpg", image_data, "image/jpeg")}
    res2 = await async_client.post("/api/media/upload", files=files_dup)
    assert res2.status_code == 409
    
    detail = res2.json()["detail"]
    assert "Duplicate file detected" in detail["message"]
    assert "duplicate_id" in detail
