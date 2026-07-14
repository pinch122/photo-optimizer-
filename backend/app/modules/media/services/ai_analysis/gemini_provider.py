"""
Gemini Vision Provider — Sprint 5 Stub.

This provider is intentionally stubbed for Sprint 5. The VisionProvider
interface is fully wired; the actual Gemini API call and structured prompt
will be implemented in Sprint 6 once the API key is configured.

Current behaviour
-----------------
- If GEMINI_API_KEY is empty  → returns None  (triggers SKIPPED_NO_PROVIDER)
- If GEMINI_API_KEY is set    → also returns None (stub) with an info log

Sprint 6 will replace the stub body of analyze() with:
    - Load image bytes
    - Call google.genai client with a structured JSON prompt
    - Parse response into AnalysisResult
    - Return populated result

To swap in a real implementation, only this file changes.
AIAnalysisService, worker.py, and the rest of the application are unaffected.
"""

from __future__ import annotations

from typing import Optional

from app.config import settings
from app.logging_config import logger
from app.modules.media.services.ai_analysis.base_provider import AnalysisResult, VisionProvider


class GeminiVisionProvider(VisionProvider):
    """
    Vision provider backed by Google Gemini multimodal models.

    Sprint 5: stubbed — returns None until Sprint 6 implementation.
    Sprint 6: will use google-genai SDK with gemini-1.5-flash or gemini-pro-vision.
    """

    _MODEL_NAME = "gemini-1.5-flash"
    _MODEL_VERSION = "001"

    def get_model_name(self) -> str:
        return self._MODEL_NAME

    def get_model_version(self) -> str:
        return self._MODEL_VERSION

    async def analyze(self, image_path: str) -> Optional[AnalysisResult]:
        """
        Sprint 5: Stub implementation.

        Returns None if no API key is configured, signalling SKIPPED_NO_PROVIDER.
        Returns None even with a key (stub), signalling SKIPPED_NO_PROVIDER until
        Sprint 6 implements the actual Gemini API call.
        """
        if not settings.GEMINI_API_KEY:
            logger.info(
                "GeminiVisionProvider: GEMINI_API_KEY not configured. "
                "Analysis will be marked SKIPPED_NO_PROVIDER. "
                "Set GEMINI_API_KEY in .env to enable Gemini analysis."
            )
            return None

        # Sprint 6: replace this block with the real Gemini API call.
        logger.info(
            f"GeminiVisionProvider: API key found but provider is stubbed (Sprint 5). "
            f"image_path={image_path}. Full implementation ships in Sprint 6."
        )
        return None
