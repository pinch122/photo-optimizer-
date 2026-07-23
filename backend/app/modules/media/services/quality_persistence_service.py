"""
Quality Persistence Service.

Handles loading a MediaAsset, evaluating its quality via QualityService.default(),
and persisting/updating the ImageQualityAssessment record in PostgreSQL.

Designed for loose coupling — called by worker tasks or API recompute endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from PIL import Image

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.logging_config import logger
from app.modules.media.models import ImageQualityAssessment, MediaAsset
from app.services.quality import QualityService


class QualityPersistenceService:
    """Orchestrates quality evaluation and persistence for a media asset."""

    @staticmethod
    async def evaluate_and_persist(
        asset_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[ImageQualityAssessment]:
        """
        Evaluate image quality for asset_id and persist ImageQualityAssessment record.

        Pipeline:
        1. Fetch MediaAsset with existing photo_metadata and ai_analysis.
        2. Build existing_metrics dict from stored ai_analysis keywords (if present).
        3. Open image with PIL.
        4. Run QualityService.default().evaluate(image, existing_metrics).
        5. Upsert ImageQualityAssessment record.
        6. Commit database transaction.

        Never raises — catches all exceptions and logs error, leaving asset intact.
        """
        logger.info(f"QualityPersistenceService: Starting quality evaluation for [{asset_id}].")
        try:
            query = (
                select(MediaAsset)
                .where(MediaAsset.id == asset_id)
                .options(
                    selectinload(MediaAsset.photo_metadata),
                    selectinload(MediaAsset.ai_analysis),
                    selectinload(MediaAsset.quality_assessment),
                )
            )
            result = await db.execute(query)
            asset = result.scalar_one_or_none()

            if not asset:
                logger.error(f"QualityPersistenceService: Asset [{asset_id}] not found in DB.")
                return None

            # Collect existing metrics if available from previous ingestion stages
            existing_metrics = {}
            if asset.ai_analysis and isinstance(asset.ai_analysis.keywords, dict):
                kw = asset.ai_analysis.keywords
                if "brightness" in kw:
                    existing_metrics["brightness"] = kw["brightness"]
                if "blur_score" in kw:
                    existing_metrics["blur_score"] = kw["blur_score"]
                if "sharpness" in kw:
                    existing_metrics["sharpness"] = kw["sharpness"]

            # Evaluate image with QualityService
            with Image.open(asset.original_path) as img:
                assessment = QualityService.default().evaluate(img, existing_metrics=existing_metrics)

            # Map issues to list of string names
            issue_strings = [issue.value for issue in assessment.issues]

            # Check if quality record already exists for upsert
            qual_query = select(ImageQualityAssessment).where(ImageQualityAssessment.media_asset_id == asset_id)
            qual_res = await db.execute(qual_query)
            record = qual_res.scalar_one_or_none()

            if record is None:
                record = ImageQualityAssessment(
                    id=uuid.uuid4(),
                    media_asset_id=asset_id,
                )
                db.add(record)

            record.overall_score = assessment.overall_score
            record.quality_grade = assessment.quality_grade.value
            record.sharpness_score = assessment.sharpness_score
            record.blur_score = assessment.blur_score_raw
            record.exposure_score = assessment.exposure_score
            record.brightness_score = assessment.brightness_raw
            record.aesthetic_score = assessment.aesthetic_score
            record.resolution_score = assessment.resolution_score
            record.confidence = assessment.confidence
            record.issues = issue_strings
            record.recommendation = assessment.recommendation
            record.provider_versions = assessment.provider_versions
            record.provider_scores = assessment.provider_scores
            record.evaluated_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info(
                f"QualityPersistenceService: Successfully persisted Quality Record for [{asset_id}] "
                f"grade='{record.quality_grade}', score={record.overall_score:.4f}."
            )
            return record

        except Exception as e:
            logger.error(
                f"QualityPersistenceService: Evaluation/persistence failed for [{asset_id}]: {e}. "
                "Continuing without quality record."
            )
            return None
