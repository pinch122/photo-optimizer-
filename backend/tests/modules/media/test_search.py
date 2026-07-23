import io
import uuid
import pytest
import asyncio
from PIL import Image
from httpx import AsyncClient
from app.modules.media.services.embedding_service import EmbeddingService
from app.modules.media.worker import process_media_task

import random

def get_mock_image_bytes(width: int = 100, height: int = 100) -> bytes:
    """
    Constructs a mock JPEG file stream with random colors to prevent SHA-256 collisions.
    """
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.mark.asyncio
async def test_text_embedding_generation():
    """
    Verifies that CLIP text query encoding generates a float vector of exactly 512 dimensions,
    and is L2-normalized.
    """
    vector = await EmbeddingService.generate_text_embedding("Find beach photos")
    assert isinstance(vector, list)
    assert len(vector) == 512
    
    magnitude = sum(coord * coord for coord in vector)
    assert abs(magnitude - 1.0) < 1e-3

@pytest.mark.asyncio
async def test_e2e_semantic_search_success(async_client: AsyncClient):
    """
    Verifies E2E semantic search:
    1. Uploads multiple mock images.
    2. Runs processing pipeline to register them in DB & Qdrant.
    3. Calls GET /api/media/search?q=query and asserts structure, pagination parameters.
    """
    # Upload first photo
    img_data_1 = get_mock_image_bytes(width=100, height=100)
    res1 = await async_client.post(
        "/api/media/upload",
        files={"file": ("beach.jpg", img_data_1, "image/jpeg")}
    )
    assert res1.status_code == 201
    asset_id_1 = uuid.UUID(res1.json()["id"])
    
    # Wait for first photo processing to complete
    success_1 = False
    for _ in range(150):
        status_check = await async_client.get(f"/api/media/{asset_id_1}/status")
        if status_check.json()["status"] == "READY":
            success_1 = True
            break
        await asyncio.sleep(0.1)
    assert success_1 is True
    
    # Upload second photo
    img_data_2 = get_mock_image_bytes(width=150, height=150)
    res2 = await async_client.post(
        "/api/media/upload",
        files={"file": ("sunset.jpg", img_data_2, "image/jpeg")}
    )
    assert res2.status_code == 201
    asset_id_2 = uuid.UUID(res2.json()["id"])
    
    # Wait for second photo processing to complete
    success_2 = False
    for _ in range(50):
        status_check = await async_client.get(f"/api/media/{asset_id_2}/status")
        if status_check.json()["status"] == "READY":
            success_2 = True
            break
        await asyncio.sleep(0.1)
    assert success_2 is True

    # Perform semantic search query
    search_res = await async_client.get("/api/media/search?q=beach&limit=10&offset=0")
    assert search_res.status_code == 200
    
    data = search_res.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert len(data["items"]) >= 2
    
    # Verify properties of items returned
    for item in data["items"]:
        assert "id" in item
        assert "filename" in item
        assert "mime_type" in item
        assert "score" in item
        assert "photo_metadata" in item
        assert item["score"] > 0.0

@pytest.mark.asyncio
async def test_search_validation_failures(async_client: AsyncClient):
    """
    Verifies HTTP Bad Request validations:
    - Missing query query parameter 'q'
    - Empty query query parameter 'q'
    - Out of range paging parameters
    """
    # Missing q parameter
    res = await async_client.get("/api/media/search")
    assert res.status_code == 422 # FastAPI query validation error
    
    # Empty query q=""
    res = await async_client.get("/api/media/search?q=")
    assert res.status_code == 422
    
    # Invalid limit (less than 1)
    res = await async_client.get("/api/media/search?q=test&limit=0")
    assert res.status_code == 422
    
    # Invalid offset (negative)
    res = await async_client.get("/api/media/search?q=test&offset=-1")
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_paginated_list_media_success(async_client: AsyncClient):
    """
    Verifies the newly implemented GET /api/media listing endpoint.
    """
    res = await async_client.get("/api/media?limit=5&offset=0")
    assert res.status_code == 200
    
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_delete_media_not_found(async_client: AsyncClient):
    """
    Verifies HTTP 404 response on deleting non-existent asset ID.
    """
    random_id = uuid.uuid4()
    res = await async_client.delete(f"/api/media/{random_id}")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_delete_media_success(async_client: AsyncClient):
    """
    Verifies full deletion logic of media:
    1. Uploads a mock image.
    2. Deletes the media by ID.
    3. Verifies that subsequent GET queries return 404.
    """
    img_data = get_mock_image_bytes(width=211, height=211)
    res = await async_client.post(
        "/api/media/upload",
        files={"file": ("to_delete.jpg", img_data, "image/jpeg")}
    )
    assert res.status_code == 201
    asset_id = res.json()["id"]

    # Delete media permanently
    del_res = await async_client.delete(f"/api/media/{asset_id}?permanent=true")
    assert del_res.status_code == 200
    assert del_res.json() == {"message": "Media permanently deleted successfully"}

    # Fetch status checks should return 404
    check_res = await async_client.get(f"/api/media/{asset_id}/status")
    assert check_res.status_code == 404


