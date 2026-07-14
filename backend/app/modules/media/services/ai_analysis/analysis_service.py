"""
AI Analysis Service — Knowledge Record Orchestrator.

Responsibilities
----------------
1. Load MediaAsset from PostgreSQL
2. Select and invoke the configured VisionProvider
3. Validate and normalize AnalysisResult
4. Upsert ImageAIAnalysis (Knowledge Record) into PostgreSQL
5. Emit structured logs at every lifecycle stage
6. Handle all failures gracefully — never raises, never blocks uploads

The service is provider-agnostic. It accepts any VisionProvider via constructor
injection, making it trivially testable with mock providers.

Usage
-----
    provider = get_default_provider()
    service = AIAnalysisService(provider)
    await service.analyze_image(asset_id, db)
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import logger
from app.modules.media.models import AnalysisStatus, AssetStatus, ImageAIAnalysis, MediaAsset
from app.modules.media.services.ai_analysis.base_provider import AnalysisResult, VisionProvider


class AIAnalysisService:
    """
    Orchestrates the AI analysis pipeline for a single media asset.

    Constructor accepts any VisionProvider — the service never references
    Gemini, GPT-4V, Claude, or any other concrete provider directly.
    """

    def __init__(self, provider: VisionProvider) -> None:
        self._provider = provider

    async def analyze_image(
        self,
        media_id: uuid.UUID,
        db: AsyncSession
    ) -> None:
        """
        Run the full AI analysis pipeline for the given media asset.

        Pipeline
        --------
        1. Load MediaAsset — abort if not found or not READY
        2. Create/update ImageAIAnalysis with PROCESSING status
        3. Call provider.analyze(image_path)
        4. On None result → mark SKIPPED_NO_PROVIDER
        5. On AnalysisResult → validate and persist Knowledge Record (COMPLETED)
        6. On any exception → mark FAILED, increment retry_count, log

        This method never raises. All errors are caught and persisted to DB.

        Parameters
        ----------
        media_id : uuid.UUID
            ID of the MediaAsset to analyze.
        db : AsyncSession
            Active async SQLAlchemy session.
        """
        logger.info(
            f"AIAnalysisService: Starting analysis for asset [{media_id}] "
            f"using provider '{self._provider.get_model_name()}'."
        )
        start_time = time.monotonic()

        # ── 1. Load MediaAsset ────────────────────────────────────────────────
        try:
            stmt = select(MediaAsset).where(MediaAsset.id == media_id)
            result = await db.execute(stmt)
            asset = result.scalar_one_or_none()

            if not asset:
                logger.error(
                    f"AIAnalysisService: Asset [{media_id}] not found. Analysis aborted."
                )
                return

            if asset.status != AssetStatus.READY:
                logger.warning(
                    f"AIAnalysisService: Asset [{media_id}] status is '{asset.status}' "
                    "(expected READY). Analysis aborted."
                )
                return

            image_path = asset.original_path

        except Exception as load_err:
            logger.error(
                f"AIAnalysisService: Failed to load asset [{media_id}]: {load_err}"
            )
            return

        # ── 2. Create/Update ImageAIAnalysis → PROCESSING ─────────────────────
        analysis_record = await self._get_or_create_record(db, media_id)
        analysis_record.processing_status = AnalysisStatus.PROCESSING.value
        analysis_record.model_name = self._provider.get_model_name()
        analysis_record.model_version = self._provider.get_model_version()
        analysis_record.retry_count = (analysis_record.retry_count or 0)

        try:
            await db.commit()
        except Exception as commit_err:
            logger.error(
                f"AIAnalysisService: Failed to set PROCESSING status for [{media_id}]: {commit_err}"
            )
            await db.rollback()
            return

        # ── 3. Call VisionProvider ────────────────────────────────────────────
        try:
            logger.info(
                f"AIAnalysisService: Invoking provider '{self._provider.get_model_name()}' "
                f"for asset [{media_id}], path={image_path}."
            )
            ai_result: Optional[AnalysisResult] = await self._provider.analyze(image_path)

        except Exception as provider_err:
            elapsed = time.monotonic() - start_time
            logger.error(
                f"AIAnalysisService: Provider '{self._provider.get_model_name()}' raised an "
                f"exception for asset [{media_id}] after {elapsed:.3f}s: {provider_err}"
            )
            await self._mark_failed(db, analysis_record, str(provider_err))
            return

        elapsed = time.monotonic() - start_time

        # ── 4. Handle None → SKIPPED_NO_PROVIDER ─────────────────────────────
        if ai_result is None:
            logger.info(
                f"AIAnalysisService: Provider returned None for asset [{media_id}] "
                f"after {elapsed:.3f}s. Marking SKIPPED_NO_PROVIDER."
            )
            analysis_record.processing_status = AnalysisStatus.SKIPPED_NO_PROVIDER.value
            analysis_record.processed_at = datetime.now(timezone.utc)
            try:
                await db.commit()
            except Exception as skip_err:
                logger.error(
                    f"AIAnalysisService: Failed to persist SKIPPED_NO_PROVIDER for "
                    f"[{media_id}]: {skip_err}"
                )
                await db.rollback()
            return

        # ── 5. Persist AnalysisResult → COMPLETED ────────────────────────────
        try:
            self._apply_result(analysis_record, ai_result)
            analysis_record.processing_status = AnalysisStatus.COMPLETED.value
            analysis_record.processed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                f"AIAnalysisService: Knowledge Record persisted for asset [{media_id}] "
                f"in {elapsed:.3f}s. Provider='{self._provider.get_model_name()}'."
            )

        except Exception as persist_err:
            logger.error(
                f"AIAnalysisService: Failed to persist Knowledge Record for [{media_id}]: "
                f"{persist_err}"
            )
            await db.rollback()
            await self._mark_failed(db, analysis_record, str(persist_err))

    # ── Private Helpers ───────────────────────────────────────────────────────

    async def _get_or_create_record(
        self,
        db: AsyncSession,
        media_id: uuid.UUID
    ) -> ImageAIAnalysis:
        """
        Return the existing ImageAIAnalysis row or create a fresh PENDING record.
        Handles the upsert pattern without needing ON CONFLICT support.
        """
        stmt = select(ImageAIAnalysis).where(ImageAIAnalysis.media_asset_id == media_id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            record = ImageAIAnalysis(
                id=uuid.uuid4(),
                media_asset_id=media_id,
                processing_status=AnalysisStatus.PENDING.value,
                retry_count=0
            )
            db.add(record)
            await db.flush()  # Assign PK without committing

        return record

    @staticmethod
    def _apply_result(record: ImageAIAnalysis, result: AnalysisResult) -> None:
        """
        Map all AnalysisResult fields onto the ImageAIAnalysis ORM record.
        Only non-None values overwrite existing fields to preserve partial data.
        """
        # Visual understanding
        if result.caption is not None:
            record.caption = result.caption
        if result.detailed_description is not None:
            record.detailed_description = result.detailed_description
        if result.scene is not None:
            record.scene = result.scene
        if result.objects is not None:
            record.objects = result.objects
        if result.activities is not None:
            record.activities = result.activities

        # Image understanding
        if result.indoor_outdoor is not None:
            record.indoor_outdoor = result.indoor_outdoor
            # Keep legacy boolean in sync
            record.is_indoor = (result.indoor_outdoor == "indoor")
        if result.weather is not None:
            record.weather = result.weather
        if result.season is not None:
            record.season = result.season
        if result.dominant_colors is not None:
            record.dominant_colors = result.dominant_colors

        # People
        if result.people_count is not None:
            record.people_count = result.people_count

        # Documents / OCR
        if result.detected_text is not None:
            record.detected_text = result.detected_text
        if result.document_type is not None:
            record.document_type = result.document_type

        # Memory understanding
        if result.event_type is not None:
            record.event_type = result.event_type
        if result.travel_event is not None:
            record.travel_event = result.travel_event
        if result.location_guess is not None:
            record.location_guess = result.location_guess
        if result.mood is not None:
            record.mood = result.mood

        # AI metadata
        if result.ai_confidence is not None:
            record.ai_confidence = result.ai_confidence
        if result.raw_response is not None:
            record.raw_response = result.raw_response

    async def _mark_failed(
        self,
        db: AsyncSession,
        record: ImageAIAnalysis,
        error_message: str
    ) -> None:
        """
        Persist FAILED status and increment retry_count.
        Does not raise — silently swallows any secondary DB failure.
        """
        try:
            record.processing_status = AnalysisStatus.FAILED.value
            record.error_message = error_message[:2000]
            record.retry_count = (record.retry_count or 0) + 1
            record.processed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(
                f"AIAnalysisService: Marked asset [{record.media_asset_id}] as FAILED. "
                f"retry_count={record.retry_count}."
            )
        except Exception as db_err:
            logger.error(
                f"AIAnalysisService: Critical — could not persist FAILED status for "
                f"[{record.media_asset_id}]: {db_err}"
            )
            await db.rollback()
