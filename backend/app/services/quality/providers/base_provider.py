"""
Abstract base class for Quality Assessment providers.

Each provider inspects an image from a different angle (classical CV, perceptual
CLIP-IQA, future NIQE/MUSIQ, etc.) and returns a normalised ProviderResult.
The QualityService fusion engine combines all provider results into a single
QualityAssessment.

To add a new provider:
1. Subclass QualityProvider.
2. Implement evaluate() and the name property.
3. Pass an instance to QualityService.__init__(providers=[...]).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional

from PIL import Image


@dataclass
class ProviderResult:
    """
    Normalised output from a single quality provider.

    All scores are in [0.0, 1.0] (higher = better quality) unless documented
    otherwise. Optional score fields are None if the provider does not measure
    that dimension or if the provider is unavailable.

    Fields
    ------
    is_available        True if the provider ran successfully; False if unavailable/failed.
    sharpness_score     Edge-definition quality; 1.0 = perfectly sharp.
    exposure_score      Correctness of exposure; 1.0 = well-exposed.
    resolution_score    Resolution adequacy; 1.0 = high resolution.
    aesthetic_score     Perceptual / aesthetic quality; 1.0 = visually appealing.
    confidence          How reliable this provider's result is [0.0–1.0].
                        0.0 = provider could not assess.
    raw_metrics         Arbitrary key→value debug data specific to this provider.
    """
    is_available:     bool = True
    sharpness_score:  Optional[float] = None
    exposure_score:   Optional[float] = None
    resolution_score: Optional[float] = None
    aesthetic_score:  Optional[float] = None
    confidence:       float = 1.0
    raw_metrics:      Dict[str, Any] = field(default_factory=dict)


class QualityProvider(ABC):
    """
    Abstract interface for quality assessment providers.

    Implementations must be stateless and thread-safe.  The evaluate() method
    may be called from a thread pool executor for async contexts.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider identifier used in provider_scores output."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Provider semver string (e.g. '1.0') stored in provider_versions metadata."""
        ...

    @abstractmethod
    def evaluate(
        self,
        image: Image.Image,
        existing_metrics: Optional[Dict[str, float]] = None,
    ) -> ProviderResult:
        """
        Assess image quality and return a normalised ProviderResult.

        Parameters
        ----------
        image
            PIL Image object. The provider must NOT close or mutate it.
        existing_metrics
            Optional pre-computed metrics dict (e.g. from the ingestion
            pipeline keywords JSON: brightness, blur_score, sharpness).
            Providers should reuse these values instead of recomputing them
            when available to avoid redundant CPU work.

        Returns
        -------
        ProviderResult
            Must never raise. On error, return a ProviderResult with
            confidence=0.0 and neutral scores (0.5) so the fusion engine
            can still produce a valid assessment from other providers.
        """
        ...
