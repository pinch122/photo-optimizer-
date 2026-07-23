"""
Classical Computer Vision quality provider.

Uses only PIL (Pillow) — no neural network, no external API.
Computes sharpness, exposure, and resolution scores from pixel statistics.

Existing metrics from the ingestion pipeline (blur_score, brightness,
sharpness stored in image_ai_analysis.keywords) are reused when provided
to avoid redundant CPU work.

Signals
-------
Sharpness   — standard deviation of edge-filtered (FIND_EDGES) grayscale
              intensities.  High stddev = sharp; low stddev = blurry.
              Normalised via a soft sigmoid centred on a typical midpoint.

Exposure    — mean grayscale brightness mapped to a bell curve centred on
              0.5 (mid-grey = perfectly exposed).  0.0 at either extreme
              (pure black or pure white).  This produces a score in [0.0, 1.0]
              where 1.0 means correctly exposed.

Resolution  — total megapixels mapped to a clamped linear ramp.
              0 MP = 0.0,  ≥ 12 MP = 1.0.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from PIL import Image, ImageFilter, ImageStat

from .base_provider import ProviderResult, QualityProvider


# Normalisation constants (calibrated on typical consumer photos)
_SHARPNESS_SOFT_K = 0.12       # controls sigmoid steepness
_SHARPNESS_MIDPOINT = 20.0     # stddev value that maps to ~0.5 score
_RESOLUTION_MAX_MP = 12.0      # megapixels that map to score 1.0


def _sigmoid(x: float, k: float = 1.0, midpoint: float = 0.0) -> float:
    """Logistic sigmoid: maps any real value to (0, 1)."""
    try:
        return 1.0 / (1.0 + math.exp(-k * (x - midpoint)))
    except OverflowError:
        return 0.0 if x < midpoint else 1.0


def _exposure_score(brightness: float) -> float:
    """
    Bell-curve mapping: 0.5 brightness → 1.0, extremes → 0.0.

    Uses a cosine kernel so the transition is smooth and the score
    is not arbitrarily penalised at ±5% from centre.
    """
    # Map [0, 1] to [-π, π] centred at 0.5
    phase = (brightness - 0.5) * 2.0 * math.pi
    return max(0.0, (math.cos(phase) + 1.0) / 2.0)


class ClassicalProvider(QualityProvider):
    """
    Classical CV quality provider using PIL pixel statistics.

    Reuses existing ingestion metrics when provided; only recomputes what
    is missing.  Safe to call from a thread pool executor.
    """

    @property
    def name(self) -> str:
        return "classical_cv"

    @property
    def version(self) -> str:
        return "1.0"

    def evaluate(
        self,
        image: Image.Image,
        existing_metrics: Optional[Dict[str, float]] = None,
    ) -> ProviderResult:
        """
        Compute sharpness, exposure, and resolution scores.

        existing_metrics keys understood:
            brightness  — float 0–1 (from ingestion quality.py)
            blur_score  — float 0–100 (higher = blurrier)
            sharpness   — float (edge stddev from ingestion quality.py)
        """
        existing = existing_metrics or {}
        raw: Dict[str, float] = {}

        try:
            # ── Resolution ──────────────────────────────────────────────────
            width, height = image.size
            megapixels = (width * height) / 1_000_000.0
            resolution_score = min(1.0, megapixels / _RESOLUTION_MAX_MP)
            raw["megapixels"] = round(megapixels, 4)
            raw["width"] = float(width)
            raw["height"] = float(height)

            # ── Brightness / Exposure ────────────────────────────────────────
            if "brightness" in existing:
                brightness = float(existing["brightness"])
                raw["brightness_source"] = 0.0   # 0 = reused
            else:
                gray = image.convert("L")
                stat = ImageStat.Stat(gray)
                brightness = stat.mean[0] / 255.0
                raw["brightness_source"] = 1.0   # 1 = recomputed

            raw["brightness"] = round(brightness, 4)
            exposure_sc = _exposure_score(brightness)
            raw["exposure_score"] = round(exposure_sc, 4)

            # ── Sharpness ────────────────────────────────────────────────────
            if "sharpness" in existing:
                # Existing sharpness is edge stddev from ingestion pipeline
                edge_stddev = float(existing["sharpness"])
                raw["sharpness_source"] = 0.0
            else:
                gray = image.convert("L")
                edges = gray.filter(ImageFilter.FIND_EDGES)
                # Crop border margin to remove PIL convolution border artifacts
                crop_margin = min(2, width // 4, height // 4)
                if crop_margin > 0:
                    edges = edges.crop((crop_margin, crop_margin, width - crop_margin, height - crop_margin))
                edge_stat = ImageStat.Stat(edges)
                edge_stddev = edge_stat.stddev[0]
                raw["sharpness_source"] = 1.0

            # Normalise via soft sigmoid
            sharpness_sc = _sigmoid(edge_stddev, k=_SHARPNESS_SOFT_K, midpoint=_SHARPNESS_MIDPOINT)
            raw["edge_stddev"] = round(edge_stddev, 4)
            raw["sharpness_score"] = round(sharpness_sc, 4)

            # ── Blur raw (for issue detection in fusion) ──────────────────────
            if "blur_score" in existing:
                raw["blur_score"] = float(existing["blur_score"])
            else:
                # Derive from edge_stddev (inverse proxy — same formula as ingestion)
                raw["blur_score"] = round(max(0.0, 100.0 - edge_stddev * 3.0), 4)

            return ProviderResult(
                is_available=True,
                sharpness_score=round(sharpness_sc, 4),
                exposure_score=round(exposure_sc, 4),
                resolution_score=round(resolution_score, 4),
                aesthetic_score=None,   # Classical CV does not measure aesthetics; None avoids fake scores
                confidence=1.0,
                raw_metrics=raw,
            )

        except Exception as exc:  # pragma: no cover — defensive fallback
            return ProviderResult(
                is_available=False,
                confidence=0.0,
                raw_metrics={"error": str(exc)},
            )
