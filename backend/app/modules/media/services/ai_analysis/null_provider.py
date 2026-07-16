"""
Null Vision Provider — explicit no-op.

Used when AI analysis is administratively disabled via AI_ANALYSIS_ENABLED=False
or VISION_PROVIDER=null. Returns None from analyze(), which the AIAnalysisService
interprets as SKIPPED_NO_PROVIDER.

This is distinct from a failure — it is an intentional skip.
"""

from __future__ import annotations

from typing import Optional

from app.logging_config import logger
from app.modules.media.services.ai_analysis.base_provider import AnalysisResult, VisionProvider


class NullProvider(VisionProvider):
    """
    No-op VisionProvider. Always returns None.

    Used when:
    - AI_ANALYSIS_ENABLED is False in settings
    - VISION_PROVIDER is explicitly set to "null"
    - No valid provider is available for the configured key
    """

    def get_model_name(self) -> str:
        return "null"

    def get_model_version(self) -> str:
        return "0"

    async def analyze(
        self,
        image_path: str,
        image_context: Optional[dict] = None,
    ) -> Optional[AnalysisResult]:
        logger.debug(
            f"NullProvider: analyze() called for image_path={image_path}. "
            "Returning None (analysis disabled)."
        )
        return None
