"""
Gemini Vision Provider.

This provider implements the VisionProvider interface using the Google GenAI SDK.
It calls the Gemini API to analyze an image and return raw JSON conforming to the schema.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from app.config import settings
from app.logging_config import logger
from app.modules.media.services.ai_analysis.base_provider import AnalysisResult, VisionProvider


class GeminiVisionProvider(VisionProvider):
    """
    Vision provider backed by Google Gemini multimodal models.
    """

    _MODEL_NAME = "gemini-1.5-flash"
    _MODEL_VERSION = "001"

    def get_model_name(self) -> str:
        return self._MODEL_NAME

    def get_model_version(self) -> str:
        return self._MODEL_VERSION

    async def analyze(self, image_path: str) -> Optional[AnalysisResult]:
        """
        Run Gemini vision analysis on the image at image_path.

        If GEMINI_API_KEY is not configured, logs an info message and returns None
        (triggers SKIPPED_NO_PROVIDER status).
        """
        if not settings.GEMINI_API_KEY:
            logger.info(
                "GeminiVisionProvider: GEMINI_API_KEY not configured. "
                "Analysis will be marked SKIPPED_NO_PROVIDER. "
                "Set GEMINI_API_KEY in .env to enable Gemini analysis."
            )
            return None

        logger.info(
            f"AIAnalysisService: Analysis started. Provider selected: '{self.get_model_name()}' (version: '{self.get_model_version()}')."
        )

        from PIL import Image
        from google import genai
        from google.genai import types
        from app.modules.media.services.ai_analysis.prompt_template import get_system_prompt, build_analysis_prompt
        from app.modules.media.services.ai_analysis.response_parser import parse_knowledge_record

        system_prompt = get_system_prompt()
        user_prompt = build_analysis_prompt(None)

        logger.info(f"GeminiVisionProvider: System prompt version length: {len(system_prompt)} characters.")

        start_time = time.monotonic()
        try:
            # Load image using PIL
            image = Image.open(image_path)

            # Initialize the genai Client
            client = genai.Client(api_key=settings.GEMINI_API_KEY)

            # Execute API call in a separate thread to prevent blocking the asyncio event loop
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self._MODEL_NAME,
                contents=[image, user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                )
            )

            latency = time.monotonic() - start_time
            logger.info(f"GeminiVisionProvider: Gemini API call succeeded. Latency: {latency:.3f}s")

            raw_text = response.text
            if not raw_text:
                raise ValueError("Gemini API returned an empty response text body.")

            logger.info("GeminiVisionProvider: Handing raw text response to parser for validation and normalization.")
            analysis_result = parse_knowledge_record(raw_text)
            logger.info("GeminiVisionProvider: Parsing, validation, and normalization succeeded.")

            return analysis_result

        except Exception as e:
            latency = time.monotonic() - start_time
            logger.error(
                f"GeminiVisionProvider: Error occurred during analysis after {latency:.3f}s: {e}"
            )
            raise
