"""
AI Understanding Engine — Provider Abstraction Layer.

Defines VisionProvider, the abstract interface every vision model must implement,
and AnalysisResult, the normalized data contract that decouples provider output
from the Knowledge Record schema.

Design intent
-------------
The rest of the application (AIAnalysisService, worker, router) depends ONLY on
these interfaces. Concrete implementations (Gemini, GPT-4V, Claude, Florence)
live in separate files and are selected by the provider factory.

To add a new provider:
    1. Create a new file, e.g. gpt4v_provider.py
    2. Subclass VisionProvider
    3. Implement analyze(), get_model_name(), get_model_version()
    4. Register it in provider_factory.py

No changes to AIAnalysisService or any caller are ever needed.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AnalysisResult:
    """
    Normalized output contract for all VisionProvider implementations.

    Every field maps 1-to-1 with an ImageAIAnalysis column.
    All fields are Optional so partial results are valid — providers may
    populate only the fields they support.
    """
    # Visual understanding
    caption: Optional[str] = None
    detailed_description: Optional[str] = None
    scene: Optional[str] = None
    objects: Optional[List[str]] = field(default=None)
    activities: Optional[List[str]] = field(default=None)

    # Image understanding
    indoor_outdoor: Optional[str] = None          # "indoor" | "outdoor" | "unknown"
    weather: Optional[str] = None
    season: Optional[str] = None
    dominant_colors: Optional[List[str]] = field(default=None)

    # People
    people_count: Optional[int] = None

    # Documents / OCR
    detected_text: Optional[str] = None
    document_type: Optional[str] = None

    # Memory understanding
    event_type: Optional[str] = None
    travel_event: Optional[bool] = None
    location_guess: Optional[str] = None
    mood: Optional[str] = None

    # AI metadata
    ai_confidence: Optional[float] = None         # 0.0 – 1.0
    raw_response: Optional[dict] = None           # Full provider JSON for debugging


class VisionProvider(abc.ABC):
    """
    Abstract interface for any vision AI model provider.

    Contract
    --------
    - analyze()          : accepts a local file path, returns AnalysisResult or None
    - get_model_name()   : human-readable model identifier ("gemini-1.5-flash")
    - get_model_version(): version string for audit trail ("001" / "2024-05-02")

    Returning None from analyze() signals the engine to mark the record as
    SKIPPED_NO_PROVIDER instead of FAILED. Raising an exception signals FAILED.
    """

    @abc.abstractmethod
    async def analyze(self, image_path: str) -> Optional[AnalysisResult]:
        """
        Run vision analysis on the image at image_path.

        Parameters
        ----------
        image_path : str
            Absolute path to the image file on the local filesystem.

        Returns
        -------
        AnalysisResult
            Populated result on success.
        None
            If the provider is not configured / not applicable (triggers SKIPPED_NO_PROVIDER).

        Raises
        ------
        Exception
            Any unhandled exception triggers FAILED status and retry eligibility.
        """
        ...

    @abc.abstractmethod
    def get_model_name(self) -> str:
        """Return the canonical model identifier, e.g. 'gemini-1.5-flash'."""
        ...

    @abc.abstractmethod
    def get_model_version(self) -> str:
        """Return the model version string for audit/logging, e.g. '001'."""
        ...
