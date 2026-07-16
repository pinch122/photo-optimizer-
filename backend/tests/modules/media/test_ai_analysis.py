"""
Unit tests for the AI Understanding Engine.

Uses the existing conftest.py patterns:
- SQLite in-memory database (via test_engine from conftest)
- Mock sentence-transformers
- No external services contacted

Note on DB isolation
--------------------
aiosqlite in-memory databases are connection-scoped. A fresh test_session_local()
may get a different connection than the one used by the autouse fixture's create_all.
Each DB-touching test calls _setup_db() first to ensure tables exist on the
same connection the test session will use.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.modules.media.models import (
    AnalysisStatus,
    AssetStatus,
    ImageAIAnalysis,
    MediaAsset,
    MediaType,
)
from app.modules.media.services.ai_analysis.analysis_service import AIAnalysisService
from app.modules.media.services.ai_analysis.base_provider import AnalysisResult, VisionProvider
from app.modules.media.services.ai_analysis.null_provider import NullProvider


# ─── Mock Providers ──────────────────────────────────────────────────────────

class MockSuccessProvider(VisionProvider):
    """Returns a fully populated AnalysisResult."""

    def get_model_name(self) -> str:
        return "mock-vision-v1"

    def get_model_version(self) -> str:
        return "test"

    async def analyze(
        self,
        image_path: str,
        image_context: Optional[dict] = None,
    ) -> Optional[AnalysisResult]:
        return AnalysisResult(
            caption="A beautiful mountain landscape at sunset",
            detailed_description="Wide shot of snow-capped mountains reflecting in a calm lake.",
            scene="mountain",
            objects=["mountain", "lake", "sky"],
            activities=["photography"],
            indoor_outdoor="outdoor",
            weather="clear",
            season="autumn",
            dominant_colors=["#4a90e2", "#f5a623", "#ffffff"],
            people_count=0,
            event_type="travel",
            travel_event=True,
            location_guess="Swiss Alps",
            mood="peaceful",
            ai_confidence=0.93,
        )


class MockFailingProvider(VisionProvider):
    """Always raises an exception."""

    def get_model_name(self) -> str:
        return "mock-failing-v1"

    def get_model_version(self) -> str:
        return "test"

    async def analyze(
        self,
        image_path: str,
        image_context: Optional[dict] = None,
    ) -> Optional[AnalysisResult]:
        raise RuntimeError("Simulated provider API failure")


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _setup_db() -> None:
    """
    Ensure all ORM tables exist on the test engine before each DB-touching test.

    aiosqlite :memory: databases are connection-scoped. The conftest autouse
    fixture calls create_all on one connection; a fresh test_session_local()
    may get a different connection (empty DB). Calling create_all here before
    opening a session guarantees the tables exist.
    """
    from app.database import Base
    from tests.conftest import test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _create_ready_asset(db) -> MediaAsset:
    """Insert a READY MediaAsset into the test DB and return it."""
    asset = MediaAsset(
        id=uuid.uuid4(),
        filename="test_image.jpg",
        mime_type="image/jpeg",
        media_type=MediaType.PHOTO,
        file_size=12345,
        file_hash=uuid.uuid4().hex,
        status=AssetStatus.READY,
        original_path="/storage/originals/test_image.jpg",
        taken_at=datetime.now(timezone.utc),
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


# ─── Provider-only Tests (no DB) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_null_provider_returns_none():
    """NullProvider.analyze() must return None regardless of input."""
    provider = NullProvider()
    result = await provider.analyze("/any/path.jpg")
    assert result is None


@pytest.mark.asyncio
async def test_null_provider_identity():
    """NullProvider reports correct model name and version."""
    provider = NullProvider()
    assert provider.get_model_name() == "null"
    assert provider.get_model_version() == "0"


@pytest.mark.asyncio
async def test_provider_factory_returns_null_when_disabled():
    """get_default_provider() must return NullProvider when AI_ANALYSIS_ENABLED=False."""
    from app.modules.media.services.ai_analysis.null_provider import NullProvider as NP
    from app.modules.media.services.ai_analysis.provider_factory import get_default_provider

    with patch("app.modules.media.services.ai_analysis.provider_factory.settings") as ms:
        ms.AI_ANALYSIS_ENABLED = False
        ms.VISION_PROVIDER = "gemini"
        provider = get_default_provider()

    assert isinstance(provider, NP)


@pytest.mark.asyncio
async def test_provider_factory_returns_null_for_null_provider():
    """get_default_provider() must return NullProvider when VISION_PROVIDER=null."""
    from app.modules.media.services.ai_analysis.null_provider import NullProvider as NP
    from app.modules.media.services.ai_analysis.provider_factory import get_default_provider

    with patch("app.modules.media.services.ai_analysis.provider_factory.settings") as ms:
        ms.AI_ANALYSIS_ENABLED = True
        ms.VISION_PROVIDER = "null"
        provider = get_default_provider()

    assert isinstance(provider, NP)


@pytest.mark.asyncio
async def test_provider_factory_returns_gemini_provider():
    """get_default_provider() must return GeminiVisionProvider when VISION_PROVIDER=gemini."""
    from app.modules.media.services.ai_analysis.gemini_provider import GeminiVisionProvider
    from app.modules.media.services.ai_analysis.provider_factory import get_default_provider

    with patch("app.modules.media.services.ai_analysis.provider_factory.settings") as ms:
        ms.AI_ANALYSIS_ENABLED = True
        ms.VISION_PROVIDER = "gemini"
        provider = get_default_provider()

    assert isinstance(provider, GeminiVisionProvider)


# ─── Service Tests (require DB) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analysis_service_skips_when_provider_returns_none():
    """
    When provider returns None, AIAnalysisService must:
    - Create ImageAIAnalysis record
    - Set processing_status = SKIPPED_NO_PROVIDER
    - Not raise
    """
    await _setup_db()
    from tests.conftest import test_session_local

    async with test_session_local() as db:
        asset = await _create_ready_asset(db)
        service = AIAnalysisService(NullProvider())
        await service.analyze_image(asset.id, db)

        stmt = select(ImageAIAnalysis).where(ImageAIAnalysis.media_asset_id == asset.id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.processing_status == AnalysisStatus.SKIPPED_NO_PROVIDER.value
        assert record.processed_at is not None


@pytest.mark.asyncio
async def test_analysis_service_creates_completed_record():
    """
    When provider returns a full AnalysisResult, AIAnalysisService must:
    - Persist all fields to ImageAIAnalysis
    - Set processing_status = COMPLETED
    - Set model_name and model_version
    """
    await _setup_db()
    from tests.conftest import test_session_local

    async with test_session_local() as db:
        asset = await _create_ready_asset(db)
        service = AIAnalysisService(MockSuccessProvider())
        await service.analyze_image(asset.id, db)

        stmt = select(ImageAIAnalysis).where(ImageAIAnalysis.media_asset_id == asset.id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.processing_status == AnalysisStatus.COMPLETED.value
        assert record.model_name == "mock-vision-v1"
        assert record.caption == "A beautiful mountain landscape at sunset"
        assert record.scene == "mountain"
        assert record.indoor_outdoor == "outdoor"
        assert record.is_indoor is False
        assert record.people_count == 0
        assert record.travel_event is True
        assert record.location_guess == "Swiss Alps"
        assert record.dominant_colors == ["#4a90e2", "#f5a623", "#ffffff"]
        assert record.ai_confidence == pytest.approx(0.93)
        assert record.processed_at is not None


@pytest.mark.asyncio
async def test_analysis_service_marks_failed_on_provider_exception():
    """
    When provider raises an exception, AIAnalysisService must:
    - Set processing_status = FAILED
    - Persist error_message
    - Increment retry_count to 1
    - NOT raise
    """
    await _setup_db()
    from tests.conftest import test_session_local

    async with test_session_local() as db:
        asset = await _create_ready_asset(db)
        service = AIAnalysisService(MockFailingProvider())

        await service.analyze_image(asset.id, db)  # Must not raise

        stmt = select(ImageAIAnalysis).where(ImageAIAnalysis.media_asset_id == asset.id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.processing_status == AnalysisStatus.FAILED.value
        assert record.error_message is not None
        assert "Simulated provider API failure" in record.error_message
        assert record.retry_count == 1


@pytest.mark.asyncio
async def test_analysis_service_aborts_for_non_ready_asset():
    """
    AIAnalysisService must not create an ImageAIAnalysis record
    if the asset status is not READY.
    """
    await _setup_db()
    from tests.conftest import test_session_local

    async with test_session_local() as db:
        asset = MediaAsset(
            id=uuid.uuid4(),
            filename="processing.jpg",
            mime_type="image/jpeg",
            media_type=MediaType.PHOTO,
            file_size=999,
            file_hash=uuid.uuid4().hex,
            status=AssetStatus.PROCESSING,
            original_path="/storage/originals/processing.jpg",
            taken_at=datetime.now(timezone.utc),
        )
        db.add(asset)
        await db.commit()

        service = AIAnalysisService(MockSuccessProvider())
        await service.analyze_image(asset.id, db)

        stmt = select(ImageAIAnalysis).where(ImageAIAnalysis.media_asset_id == asset.id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        assert record is None


@pytest.mark.asyncio
async def test_analysis_service_aborts_for_unknown_asset():
    """AIAnalysisService must not raise if the asset ID does not exist."""
    await _setup_db()
    from tests.conftest import test_session_local

    async with test_session_local() as db:
        service = AIAnalysisService(MockSuccessProvider())
        await service.analyze_image(uuid.uuid4(), db)  # Must not raise
