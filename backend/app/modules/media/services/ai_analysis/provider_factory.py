"""
Provider Factory — centralized VisionProvider selection.

Reads application settings to determine which VisionProvider to return.
All provider construction logic lives here so that AIAnalysisService
and the worker never import provider classes directly.

Extension pattern (Sprint 6+)
------------------------------
To add a new provider:
    1. Add a new value to settings.VISION_PROVIDER (e.g. "gpt4v")
    2. Import the new provider class below
    3. Add an elif branch in get_default_provider()

Nothing else in the codebase changes.

Current routing table
---------------------
VISION_PROVIDER=gemini   → GeminiVisionProvider  (Sprint 5: stub)
VISION_PROVIDER=null     → NullProvider
AI_ANALYSIS_ENABLED=False → NullProvider (regardless of VISION_PROVIDER)
"""

from __future__ import annotations

from app.config import settings
from app.logging_config import logger
from app.modules.media.services.ai_analysis.base_provider import VisionProvider


def get_default_provider() -> VisionProvider:
    """
    Return the active VisionProvider based on current application settings.

    Returns
    -------
    VisionProvider
        A concrete provider instance ready for use by AIAnalysisService.
    """
    # Lazy imports prevent circular dependencies and keep startup fast
    from app.modules.media.services.ai_analysis.null_provider import NullProvider
    from app.modules.media.services.ai_analysis.gemini_provider import GeminiVisionProvider

    if not settings.AI_ANALYSIS_ENABLED:
        logger.info("ProviderFactory: AI_ANALYSIS_ENABLED=False. Returning NullProvider.")
        return NullProvider()

    provider_name = settings.VISION_PROVIDER.lower().strip()

    if provider_name == "gemini":
        logger.info("ProviderFactory: Selecting GeminiVisionProvider.")
        return GeminiVisionProvider()

    if provider_name == "null":
        logger.info("ProviderFactory: VISION_PROVIDER=null. Returning NullProvider.")
        return NullProvider()

    # Unknown provider — warn and fall back to NullProvider
    logger.warning(
        f"ProviderFactory: Unknown VISION_PROVIDER='{provider_name}'. "
        "Falling back to NullProvider. Check your .env configuration."
    )
    return NullProvider()
