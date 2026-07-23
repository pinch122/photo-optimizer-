import io
import uuid
import pytest
from PIL import Image
from httpx import AsyncClient

def get_mock_image_bytes(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.mark.asyncio
async def test_soft_delete_and_restore_workflow(async_client: AsyncClient):
    """
    Test Recycle Bin / Soft deletion pipeline:
    1. Upload image
    2. Soft delete (moves to Recycle Bin)
    3. Verify absent from GET /api/media
    4. Verify present in GET /api/media/trash
    5. Restore image from trash
    6. Verify present in GET /api/media
    """
    img_bytes = get_mock_image_bytes(width=120, height=120)
    upload_res = await async_client.post(
        "/api/media/upload",
        files={"file": ("trash_test.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 1. Verify visible in gallery list
    gallery_res = await async_client.get("/api/media")
    assert gallery_res.status_code == 200
    gallery_ids = [item["id"] for item in gallery_res.json()["items"]]
    assert asset_id in gallery_ids

    # 2. Soft delete asset
    del_res = await async_client.delete(f"/api/media/{asset_id}")
    assert del_res.status_code == 200

    # 3. Verify hidden from active gallery list
    gallery_res_2 = await async_client.get("/api/media")
    assert gallery_res_2.status_code == 200
    gallery_ids_2 = [item["id"] for item in gallery_res_2.json()["items"]]
    assert asset_id not in gallery_ids_2

    # 4. Verify listed in trash
    trash_res = await async_client.get("/api/media/trash")
    assert trash_res.status_code == 200
    trash_items = trash_res.json()["items"]
    trash_ids = [item["id"] for item in trash_items]
    assert asset_id in trash_ids
    
    # Check trash count endpoint
    count_res = await async_client.get("/api/media/trash/count")
    assert count_res.status_code == 200
    assert count_res.json()["count"] >= 1

    # 5. Restore asset from trash
    restore_res = await async_client.post(f"/api/media/{asset_id}/restore")
    assert restore_res.status_code == 200

    # 6. Verify restored asset is back in active gallery list
    gallery_res_3 = await async_client.get("/api/media")
    assert gallery_res_3.status_code == 200
    gallery_ids_3 = [item["id"] for item in gallery_res_3.json()["items"]]
    assert asset_id in gallery_ids_3


@pytest.mark.asyncio
async def test_permanent_delete_workflow(async_client: AsyncClient):
    """
    Test permanent deletion of asset:
    1. Upload image
    2. Permanent delete via permanent=true flag
    3. Verify 404 on GET /api/media/{id}
    """
    img_bytes = get_mock_image_bytes(width=140, height=140)
    upload_res = await async_client.post(
        "/api/media/upload",
        files={"file": ("perm_delete.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    del_res = await async_client.delete(f"/api/media/{asset_id}?permanent=true")
    assert del_res.status_code == 200
    assert "permanently deleted" in del_res.json()["message"]

    get_res = await async_client.get(f"/api/media/{asset_id}")
    assert get_res.status_code == 404
