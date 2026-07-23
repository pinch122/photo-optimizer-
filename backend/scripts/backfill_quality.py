"""
Backfill script to process quality assessments for all existing media assets in the database.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.modules.media.models import MediaAsset, ImageQualityAssessment
from app.modules.media.services.quality_persistence_service import QualityPersistenceService
from app.logging_config import logger


async def run_backfill():
    start_time = time.perf_counter()
    async with async_session() as db:
        # Query assets missing quality assessment
        stmt = (
            select(MediaAsset)
            .outerjoin(ImageQualityAssessment, MediaAsset.id == ImageQualityAssessment.media_asset_id)
            .where(ImageQualityAssessment.id.is_(None))
        )
        res = await db.execute(stmt)
        unprocessed_assets = res.scalars().all()
        total_unprocessed = len(unprocessed_assets)

        logger.info(f"Quality Backfill: Found {total_unprocessed} assets requiring quality assessment.")
        print(f"Quality Backfill: Found {total_unprocessed} assets requiring quality assessment.")

        if total_unprocessed == 0:
            print("All assets already have quality assessments. Nothing to backfill.")
            return

        success_count = 0
        failed_count = 0

        for idx, asset in enumerate(unprocessed_assets, 1):
            try:
                record = await QualityPersistenceService.evaluate_and_persist(asset.id, db)
                if record:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Quality Backfill: Exception processing asset [{asset.id}]: {e}")

            if idx % 50 == 0 or idx == total_unprocessed:
                print(f"Quality Backfill Progress: [{idx}/{total_unprocessed}] (Success: {success_count}, Failed: {failed_count})")

        duration = time.perf_counter() - start_time
        msg = f"Quality Backfill Complete in {duration:.2f}s! Total: {total_unprocessed}, Success: {success_count}, Failed: {failed_count}"
        logger.info(msg)
        print(msg)


if __name__ == "__main__":
    asyncio.run(run_backfill())
