"""
Integration tests for Quality Assessment Engine DB persistence, worker failure tolerance,
and REST API endpoints.
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.database import Base
from app.modules.media.models import ImageQualityAssessment, MediaAsset, AssetStatus
from app.modules.media.services.quality_persistence_service import QualityPersistenceService
from tests.conftest import test_session_local as _test_session_local, test_engine


def get_mock_image_bytes(width: int = 120, height: int = 120) -> bytes:
    """Helper generating in-memory JPEG bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _setup_db() -> None:
    """Ensure database tables exist on the test SQLite engine before running test queries."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_quality_assessment_persisted_during_ingestion(async_client: AsyncClient):
    """Verifies that QualityPersistenceService evaluates quality and persists an ImageQualityAssessment record."""
    await _setup_db()
    image_data = get_mock_image_bytes(width=200, height=200)
    files = {"file": ("quality_test.jpg", image_data, "image/jpeg")}

    res = await async_client.post("/api/media/upload", files=files)
    assert res.status_code == 201
    asset_id = uuid.UUID(res.json()["id"])

    async with _test_session_local() as db:
        record = await QualityPersistenceService.evaluate_and_persist(asset_id, db)

        assert record is not None
        assert 0.0 <= record.overall_score <= 1.0
        assert record.quality_grade in ("EXCELLENT", "GOOD", "FAIR", "POOR", "VERY_POOR")
        assert record.confidence >= 0.0
        assert record.provider_versions is not None
        assert "classical_cv" in record.provider_versions

        # Verify DB query
        res = await db.execute(
            select(ImageQualityAssessment).where(ImageQualityAssessment.media_asset_id == asset_id)
        )
        fetched = res.scalar_one_or_none()
        assert fetched is not None
        assert fetched.id == record.id


@pytest.mark.asyncio
async def test_get_quality_api_endpoint(async_client: AsyncClient):
    """Verifies GET /api/media/{id}/quality returns the stored quality record from DB."""
    await _setup_db()
    image_data = get_mock_image_bytes(width=300, height=300)
    files = {"file": ("quality_endpoint.jpg", image_data, "image/jpeg")}

    res = await async_client.post("/api/media/upload", files=files)
    assert res.status_code == 201
    asset_id = uuid.UUID(res.json()["id"])

    async with _test_session_local() as db:
        await QualityPersistenceService.evaluate_and_persist(asset_id, db)

    # Call GET /api/media/{id}/quality
    qual_res = await async_client.get(f"/api/media/{asset_id}/quality")
    assert qual_res.status_code == 200

    data = qual_res.json()
    assert "overall_score" in data
    assert "quality_grade" in data
    assert "confidence" in data
    assert "evaluated_at" in data
    assert data["provider_versions"] is not None


@pytest.mark.asyncio
async def test_quality_endpoint_not_found_for_missing_asset(async_client: AsyncClient):
    """Verifies GET /api/media/{id}/quality returns 404 for unknown asset_id."""
    await _setup_db()
    dummy_id = uuid.uuid4()
    qual_res = await async_client.get(f"/api/media/{dummy_id}/quality")
    assert qual_res.status_code == 404


@pytest.mark.asyncio
async def test_worker_continues_if_quality_service_fails(async_client: AsyncClient):
    """Verifies that if QualityService.evaluate raises an exception, QualityPersistenceService logs and returns None."""
    await _setup_db()
    image_data = get_mock_image_bytes(width=150, height=150)
    files = {"file": ("quality_fail.jpg", image_data, "image/jpeg")}

    res = await async_client.post("/api/media/upload", files=files)
    assert res.status_code == 201
    asset_id = uuid.UUID(res.json()["id"])

    async with _test_session_local() as db:
        with patch(
            "app.services.quality.QualityService.evaluate",
            side_effect=RuntimeError("Simulated QualityService failure"),
        ):
            record = await QualityPersistenceService.evaluate_and_persist(asset_id, db)

        # Record is None, but no exception was raised
        assert record is None

        # Verify asset remains in database
        res = await db.execute(select(MediaAsset).where(MediaAsset.id == asset_id))
        fetched = res.scalar_one_or_none()
        assert fetched is not None


@pytest.mark.asyncio
async def test_quality_included_in_media_detail_api(async_client: AsyncClient):
    """Verifies GET /api/media/{id} includes quality_assessment field."""
    await _setup_db()
    image_data = get_mock_image_bytes(width=250, height=250)
    files = {"file": ("detail_quality.jpg", image_data, "image/jpeg")}

    res = await async_client.post("/api/media/upload", files=files)
    assert res.status_code == 201
    asset_id = uuid.UUID(res.json()["id"])

    async with _test_session_local() as db:
        await QualityPersistenceService.evaluate_and_persist(asset_id, db)

    detail_res = await async_client.get(f"/api/media/{asset_id}")
    assert detail_res.status_code == 200

    data = detail_res.json()
    assert "quality_assessment" in data
    assert data["quality_assessment"] is not None
    assert "overall_score" in data["quality_assessment"]


@pytest.mark.asyncio
async def test_reprocessing_updates_quality_metadata(async_client: AsyncClient):
    """Verifies that calling evaluate_and_persist multiple times updates existing record without duplicate keys."""
    await _setup_db()
    image_data = get_mock_image_bytes(width=180, height=180)
    files = {"file": ("reprocess_quality.jpg", image_data, "image/jpeg")}

    res = await async_client.post("/api/media/upload", files=files)
    assert res.status_code == 201
    asset_id = uuid.UUID(res.json()["id"])

    async with _test_session_local() as db:
        rec1 = await QualityPersistenceService.evaluate_and_persist(asset_id, db)
        assert rec1 is not None

        # Re-evaluate quality
        rec2 = await QualityPersistenceService.evaluate_and_persist(asset_id, db)
        assert rec2 is not None

        # Check that exactly one quality record exists for this asset
        records = (await db.execute(
            select(ImageQualityAssessment).where(ImageQualityAssessment.media_asset_id == asset_id)
        )).scalars().all()
        assert len(records) == 1
        assert records[0].id == rec1.id
