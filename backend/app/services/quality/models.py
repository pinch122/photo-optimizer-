"""
Quality Assessment Engine — Data Models.

This module defines the strongly-typed output structures, enumerations, and
configuration for the Quality Assessment Engine.  It has zero external
dependencies beyond the Python standard library so it can be safely imported
anywhere without triggering heavy model loading.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List


# ─── Issue Vocabulary ─────────────────────────────────────────────────────────

class QualityIssue(str, enum.Enum):
    """
    Detected quality problems in an image.

    Issues are returned as a list — an image may have multiple problems
    (e.g. LOW_EXPOSURE + OUT_OF_FOCUS).  Issue detection always requires
    *multiple corroborating signals*; no single metric alone triggers a flag.
    """
    LOW_EXPOSURE    = "LOW_EXPOSURE"     # Likely underexposed; dark + low aesthetic
    OVER_EXPOSURE   = "OVER_EXPOSURE"    # Likely overexposed; near-white + exposure score low
    OUT_OF_FOCUS    = "OUT_OF_FOCUS"     # Very low sharpness (missed focus)
    MOTION_BLUR     = "MOTION_BLUR"      # High blur score + low sharpness (subject/camera motion)
    LOW_RESOLUTION  = "LOW_RESOLUTION"   # Below minimum acceptable megapixels
    HIGH_NOISE      = "HIGH_NOISE"       # Excessive sensor noise (reserved for future provider)
    LENS_OBSTRUCTION = "LENS_OBSTRUCTION" # Probable lens cap / finger obstruction
    UNKNOWN         = "UNKNOWN"          # Cannot determine cause


# ─── Grade Vocabulary ──────────────────────────────────────────────────────────

class QualityGrade(str, enum.Enum):
    """
    Overall quality grade derived from the fused overall_score.

    Thresholds (see QualityService._assign_grade):
        EXCELLENT  ≥ 0.85
        GOOD       ≥ 0.70
        FAIR       ≥ 0.50
        POOR       ≥ 0.30
        VERY_POOR  <  0.30
    """
    EXCELLENT  = "EXCELLENT"
    GOOD       = "GOOD"
    FAIR       = "FAIR"
    POOR       = "POOR"
    VERY_POOR  = "VERY_POOR"


# ─── Assessment Output ────────────────────────────────────────────────────────

@dataclass
class QualityAssessment:
    """
    Structured quality assessment for a single image.

    Produced by QualityService.evaluate().  All scores are normalised to
    [0.0, 1.0] unless documented otherwise.

    Fields
    ------
    overall_score       Fused composite quality score (higher = better).
    sharpness_score     Edge-variance proxy; 1.0 = perfectly sharp.
    exposure_score      Bell-curve score centred on 0.5 brightness;
                        1.0 = perfectly exposed, 0.0 = black or pure white.
    blur_score_raw      Raw blur estimate from the ingestion pipeline
                        (higher = more blurred; 0 = sharpest possible).
    brightness_raw      Mean pixel intensity in [0.0, 1.0]; NOT used alone
                        to determine quality.
    aesthetic_score     CLIP-IQA perceptual quality estimate; 1.0 = highest.
    resolution_score    Derived from megapixel count; 1.0 = ≥ 12 MP.
    confidence          Aggregate provider confidence [0.0, 1.0].
    quality_grade       Enum grade derived from overall_score.
    issues              List of detected QualityIssues (may be empty).
    recommendation      Human-readable one-sentence summary.
    provider_scores     Per-provider breakdown dict (for debugging/logging).
    """
    overall_score:    float
    sharpness_score:  Optional[float]
    exposure_score:   Optional[float]
    blur_score_raw:   float
    brightness_raw:   float
    aesthetic_score:  Optional[float]
    resolution_score: Optional[float]
    confidence:       float
    quality_grade:    QualityGrade
    issues:           List[QualityIssue] = field(default_factory=list)
    recommendation:   str = ""
    provider_versions: Dict[str, str] = field(default_factory=dict)
    provider_scores:  Dict[str, dict] = field(default_factory=dict)


# ─── Fusion Configuration ─────────────────────────────────────────────────────

@dataclass
class QualityConfig:
    """
    Configurable weights and thresholds for the Quality Assessment Engine.

    All weights must sum to 1.0.  Thresholds control issue detection and
    grade boundaries.  Override the defaults by passing a custom QualityConfig
    to QualityService.__init__() or by loading values from app.config.

    Fusion weights
    --------------
    weight_sharpness    Contribution of sharpness / focus to overall_score.
    weight_exposure     Contribution of exposure correctness.
    weight_aesthetic    Contribution of CLIP-IQA perceptual score.
    weight_resolution   Contribution of image resolution.

    Blur thresholds (raw blur_score units — higher = blurrier)
    ---------------
    blur_threshold_very_blurry   Above this → MOTION_BLUR issue candidate.
    blur_threshold_blurry        Above this → OUT_OF_FOCUS candidate.

    Exposure thresholds (brightness in [0.0, 1.0])
    -------------------
    brightness_low_threshold     Below this → LOW_EXPOSURE candidate.
    brightness_high_threshold    Above this → OVER_EXPOSURE candidate.

    Resolution threshold
    --------------------
    min_resolution_mp            Megapixels; below → LOW_RESOLUTION issue.
    """
    # Fusion weights (must sum to 1.0)
    weight_sharpness:  float = 0.35
    weight_exposure:   float = 0.30
    weight_aesthetic:  float = 0.25
    weight_resolution: float = 0.10

    # Blur issue thresholds (raw score from ingestion; higher = blurrier)
    blur_threshold_very_blurry: float = 60.0
    blur_threshold_blurry:      float = 35.0

    # Exposure thresholds (normalised 0–1 brightness)
    brightness_low_threshold:  float = 0.15   # below = likely underexposed
    brightness_high_threshold: float = 0.92   # above = likely overexposed

    # Resolution threshold
    min_resolution_mp: float = 0.5  # megapixels

    def validate(self) -> None:
        """Raise ValueError if weights do not sum to 1.0 (±0.01 tolerance)."""
        total = (
            self.weight_sharpness +
            self.weight_exposure  +
            self.weight_aesthetic +
            self.weight_resolution
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"QualityConfig weights must sum to 1.0, got {total:.4f}"
            )
