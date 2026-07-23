"""
Rebuild AI Metadata Service.

Refreshes AI Memory Records (ImageAIAnalysis) for existing media assets:
- Reuses existing embeddings (vector embeddings in Qdrant/Postgres remain unchanged).
- Does not regenerate vector embeddings.
- Re-runs LocalVisionProvider / GeminiVisionProvider to populate rich semantic AI metadata
  (Caption, Objects, Scene, Dominant Colors, Keywords, OCR, Document Type, People Count).
"""

from __future__ import annotations

from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import logger
from app.modules.media.models import MediaAsset
from app.modules.media.services.ai_analysis.analysis_service import AIAnalysisService
from app.modules.media.services.ai_analysis.provider_factory import get_default_provider


class RebuildAIMetadataService:

    @staticmethod
    async def rebuild_all_metadata(db: AsyncSession, limit: int = 50000) -> Dict[str, Any]:
        """
        Rebuild AI Memory Records for all READY media assets in the library.
        Reuses existing embeddings and vector registrations.
        """
        logger.info("RebuildAIMetadataService: Starting batch AI metadata refresh operation...")
        provider = get_default_provider()
        analysis_service = AIAnalysisService(provider)

        stmt = select(MediaAsset).where(MediaAsset.status == "READY").limit(limit)
        res = await db.execute(stmt)
        assets = res.scalars().all()

        total = len(assets)
        success_count = 0

        for asset in assets:
            try:
                await analysis_service.analyze_image(asset.id, db)
                success_count += 1
            except Exception as e:
                logger.error(f"RebuildAIMetadataService: Failed refreshing asset [{asset.id}]: {e}")

        logger.info(f"RebuildAIMetadataService: Refresh complete. Processed {success_count}/{total} assets.")
        return {
            "status": "success",
            "total_assets": total,
            "refreshed_assets": success_count,
            "provider_used": provider.get_model_name()
        }
