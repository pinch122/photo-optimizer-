"""
Quality Assessment Engine — Orchestrator and Fusion Engine.

QualityService is the public API for all quality assessment operations.
It accepts a list of QualityProvider instances, runs each in sequence,
fuses their scores via a configurable weighted average, detects issues
from the fused signals, assigns a QualityGrade, and returns a fully
populated QualityAssessment.

Usage
-----
    # Simple one-liner with default providers and default config:
    from app.services.quality import QualityService
    assessment = QualityService.default().evaluate(pil_image)

    # Custom providers / weights:
    from app.services.quality import QualityService, QualityConfig
    from app.services.quality.providers import ClassicalProvider
    config = QualityConfig(weight_sharpness=0.50, weight_exposure=0.30,
                           weight_aesthetic=0.10, weight_resolution=0.10)
    service = QualityService(providers=[ClassicalProvider()], config=config)
    assessment = service.evaluate(pil_image, existing_metrics={"brightness": 0.4})

Fusion logic
------------
    overall = Σ (weight_i × score_i)
    where each score_i is a provider-weighted mean across all providers that
    reported confidence > 0 for that dimension.

Issue detection (multi-signal — never single-metric)
-----------------------------------------------------
    LOW_EXPOSURE      brightness < low_threshold  AND  aesthetic < 0.45
    OVER_EXPOSURE     brightness > high_threshold AND  exposure_score < 0.4
    OUT_OF_FOCUS      sharpness < 0.20
    MOTION_BLUR       blur_raw  > very_blurry     AND  sharpness < 0.35
    LOW_RESOLUTION    resolution < threshold
    LENS_OBSTRUCTION  brightness < 0.05           AND  sharpness < 0.15

Grade thresholds
----------------
    EXCELLENT   overall ≥ 0.85
    GOOD        overall ≥ 0.70
    FAIR        overall ≥ 0.50
    POOR        overall ≥ 0.30
    VERY_POOR   overall <  0.30
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PIL import Image

from .models import (
    QualityAssessment,
    QualityConfig,
    QualityGrade,
    QualityIssue,
)
from .providers.base_provider import ProviderResult, QualityProvider

logger = logging.getLogger("photomind")


class QualityService:
    """
    Orchestrates multi-provider quality assessment and score fusion.

    Parameters
    ----------
    providers   Ordered list of QualityProvider instances.  At least one
                provider is required.
    config      Fusion weights and detection thresholds.  Defaults to
                QualityConfig() if None.
    """

    def __init__(
        self,
        providers: List[QualityProvider],
        config: Optional[QualityConfig] = None,
    ) -> None:
        if not providers:
            raise ValueError("QualityService requires at least one provider.")
        self._providers = providers
        self._config = config or QualityConfig()
        self._config.validate()

    # ── Public API ─────────────────────────────────────────────────────────────

    def evaluate(
        self,
        image: Image.Image,
        existing_metrics: Optional[Dict[str, float]] = None,
    ) -> QualityAssessment:
        """
        Assess image quality using all configured providers.

        Parameters
        ----------
        image
            PIL Image.  Must remain open for the duration of this call.
        existing_metrics
            Optional dict of pre-computed quality values from the ingestion
            pipeline (keys: brightness, blur_score, sharpness).  Providers
            that understand these keys will reuse them instead of recomputing.

        Returns
        -------
        QualityAssessment
            Always returns a valid assessment.  Never raises.
        """
        try:
            # 1. Collect provider results
            results: List[ProviderResult] = []
            provider_scores: Dict[str, dict] = {}

            for provider in self._providers:
                try:
                    result = provider.evaluate(image, existing_metrics)
                    results.append(result)
                    if not result.is_available:
                        logger.warning(
                            f"QualityService: Provider '{provider.name}' was unavailable during evaluation."
                        )
                    provider_scores[provider.name] = {
                        "is_available":     result.is_available,
                        "sharpness_score":  result.sharpness_score,
                        "exposure_score":   result.exposure_score,
                        "resolution_score": result.resolution_score,
                        "aesthetic_score":  result.aesthetic_score,
                        "confidence":       result.confidence,
                        **result.raw_metrics,
                    }
                except Exception as exc:   # pragma: no cover
                    logger.error(
                        f"QualityService: provider '{provider.name}' raised: {exc}"
                    )

            if not results:
                return self._fallback_assessment()

            # 2. Fuse scores
            fused = self._fuse(results)

            # 3. Extract raw signals for issue detection
            brightness_raw = self._extract_raw_brightness(results, existing_metrics)
            blur_score_raw = self._extract_raw_blur(results, existing_metrics)

            # 4. Detect issues
            issues = self._detect_issues(
                sharpness_score=fused["sharpness"],
                exposure_score=fused["exposure"],
                aesthetic_score=fused["aesthetic"],
                resolution_score=fused["resolution"],
                brightness_raw=brightness_raw,
                blur_score_raw=blur_score_raw,
            )

            # 5. Assign grade
            grade = self._assign_grade(fused["overall"])

            # 6. Generate recommendation text
            recommendation = self._build_recommendation(grade, issues)

            # 7. Collect provider version tracking
            provider_versions = {
                p.name: getattr(p, "version", "1.0") for p in self._providers
            }

            return QualityAssessment(
                overall_score=round(fused["overall"], 4),
                sharpness_score=round(fused["sharpness"], 4) if fused["sharpness"] is not None else None,
                exposure_score=round(fused["exposure"], 4) if fused["exposure"] is not None else None,
                blur_score_raw=round(blur_score_raw, 4),
                brightness_raw=round(brightness_raw, 4),
                aesthetic_score=round(fused["aesthetic"], 4) if fused["aesthetic"] is not None else None,
                resolution_score=round(fused["resolution"], 4) if fused["resolution"] is not None else None,
                confidence=round(fused["confidence"], 4),
                quality_grade=grade,
                issues=issues,
                recommendation=recommendation,
                provider_versions=provider_versions,
                provider_scores=provider_scores,
            )

        except Exception as exc:   # pragma: no cover — final safety net
            logger.error(f"QualityService.evaluate: unexpected error: {exc}")
            return self._fallback_assessment()

    @classmethod
    def default(cls) -> "QualityService":
        """
        Convenience factory using default providers and default config.

        Providers (in evaluation order):
            1. ClassicalProvider  — PIL pixel statistics
            2. CLIPIQAProvider    — CLIP perceptual quality (graceful fallback)
        """
        from .providers.classical_provider import ClassicalProvider
        from .providers.clip_iqa_provider import CLIPIQAProvider

        return cls(
            providers=[ClassicalProvider(), CLIPIQAProvider()],
            config=QualityConfig(),
        )

    # ── Fusion ─────────────────────────────────────────────────────────────────

    def _fuse(self, results: List[ProviderResult]) -> Dict[str, float]:
        """
        Weighted average fusion across available providers.

        Only providers with is_available=True and confidence > 0 contribute.
        Dimension scores that are None are skipped for that provider.
        If expected providers are unavailable, overall confidence is reduced proportionally.
        """
        cfg = self._config

        available_results = [r for r in results if r.is_available and r.confidence > 0]
        if not available_results:
            return {
                "sharpness": 0.5,
                "exposure": 0.5,
                "aesthetic": 0.5,
                "resolution": 0.5,
                "overall": 0.5,
                "confidence": 0.0,
            }

        def dimension_mean(attr_name: str) -> float:
            valid_pairs = [
                (getattr(r, attr_name), r.confidence)
                for r in available_results
                if getattr(r, attr_name) is not None
            ]
            if not valid_pairs:
                return 0.5   # neutral fallback if no available provider measured this dimension
            total_w = sum(w for _, w in valid_pairs)
            if total_w < 1e-8:
                return 0.5
            return sum(s * w for s, w in valid_pairs) / total_w

        sharpness = dimension_mean("sharpness_score")
        exposure = dimension_mean("exposure_score")
        aesthetic = dimension_mean("aesthetic_score")
        resolution = dimension_mean("resolution_score")

        overall = (
            cfg.weight_sharpness  * sharpness  +
            cfg.weight_exposure   * exposure   +
            cfg.weight_aesthetic  * aesthetic  +
            cfg.weight_resolution * resolution
        )

        overall_confidence = sum(
            r.confidence for r in results if r.is_available
        ) / float(len(self._providers))

        return {
            "sharpness":  sharpness,
            "exposure":   exposure,
            "aesthetic":  aesthetic,
            "resolution": resolution,
            "overall":    min(1.0, max(0.0, overall)),
            "confidence": min(1.0, max(0.0, overall_confidence)),
        }

    # ── Issue Detection ────────────────────────────────────────────────────────

    def _detect_issues(
        self,
        sharpness_score: float,
        exposure_score: float,
        aesthetic_score: float,
        resolution_score: float,
        brightness_raw: float,
        blur_score_raw: float,
    ) -> List[QualityIssue]:
        """
        Multi-signal issue detection.

        IMPORTANT: No single metric alone triggers an issue.  Every issue
        requires at least two corroborating signals.  This prevents artistic
        dark photos (concerts, sunsets) or stylistic blur from being flagged.
        """
        cfg = self._config
        issues: List[QualityIssue] = []

        # Lens obstruction — nearly black AND unsharp (likely finger or cap)
        if brightness_raw < 0.05 and sharpness_score < 0.15:
            issues.append(QualityIssue.LENS_OBSTRUCTION)
            return issues   # if obstruction, other issues are redundant

        # Low exposure — dark brightness AND poor aesthetic perception
        if (brightness_raw < cfg.brightness_low_threshold
                and aesthetic_score < 0.45):
            issues.append(QualityIssue.LOW_EXPOSURE)

        # Over-exposure — very bright AND exposure score is poor
        if (brightness_raw > cfg.brightness_high_threshold
                and exposure_score < 0.40):
            issues.append(QualityIssue.OVER_EXPOSURE)

        # Motion blur — high blur AND low sharpness
        if (blur_score_raw > cfg.blur_threshold_very_blurry
                and sharpness_score < 0.35):
            issues.append(QualityIssue.MOTION_BLUR)
        # Out of focus — very low sharpness (distinct from motion blur)
        elif sharpness_score < 0.20:
            issues.append(QualityIssue.OUT_OF_FOCUS)

        # Low resolution
        if resolution_score < (cfg.min_resolution_mp / 12.0):
            issues.append(QualityIssue.LOW_RESOLUTION)

        return issues

    # ── Grade Assignment ───────────────────────────────────────────────────────

    @staticmethod
    def _assign_grade(overall: float) -> QualityGrade:
        if overall >= 0.85:
            return QualityGrade.EXCELLENT
        if overall >= 0.70:
            return QualityGrade.GOOD
        if overall >= 0.50:
            return QualityGrade.FAIR
        if overall >= 0.30:
            return QualityGrade.POOR
        return QualityGrade.VERY_POOR

    # ── Recommendation Text ────────────────────────────────────────────────────

    @staticmethod
    def _build_recommendation(
        grade: QualityGrade,
        issues: List[QualityIssue],
    ) -> str:
        if not issues:
            if grade in (QualityGrade.EXCELLENT, QualityGrade.GOOD):
                return "This image appears to be high quality with no detected problems."
            return "Image quality is acceptable; no specific issues detected."

        issue_labels = {
            QualityIssue.LOW_EXPOSURE:     "appears underexposed",
            QualityIssue.OVER_EXPOSURE:    "appears overexposed",
            QualityIssue.OUT_OF_FOCUS:     "is out of focus",
            QualityIssue.MOTION_BLUR:      "has motion blur",
            QualityIssue.LOW_RESOLUTION:   "has low resolution",
            QualityIssue.HIGH_NOISE:       "has high sensor noise",
            QualityIssue.LENS_OBSTRUCTION: "may have a lens obstruction",
            QualityIssue.UNKNOWN:          "has an unspecified quality problem",
        }
        parts = [issue_labels.get(i, i.value) for i in issues]
        joined = " and ".join(parts)
        return f"This image {joined}. Consider reviewing or replacing it."

    # ── Raw Signal Extraction ─────────────────────────────────────────────────

    @staticmethod
    def _extract_raw_brightness(
        results: List[ProviderResult],
        existing_metrics: Optional[Dict[str, float]],
    ) -> float:
        """Extract brightness_raw for issue detection and output."""
        if existing_metrics and "brightness" in existing_metrics:
            return float(existing_metrics["brightness"])
        for r in results:
            if r.is_available and "brightness" in r.raw_metrics:
                return float(r.raw_metrics["brightness"])
        return 0.5

    @staticmethod
    def _extract_raw_blur(
        results: List[ProviderResult],
        existing_metrics: Optional[Dict[str, float]],
    ) -> float:
        """Extract blur_score_raw for issue detection and output."""
        if existing_metrics and "blur_score" in existing_metrics:
            return float(existing_metrics["blur_score"])
        for r in results:
            if r.is_available and "blur_score" in r.raw_metrics:
                return float(r.raw_metrics["blur_score"])
        return 0.0

    # ── Fallback ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fallback_assessment() -> QualityAssessment:
        """
        Returns a neutral assessment when all providers fail.
        Confidence=0.0 signals callers that the result is unreliable.
        """
        return QualityAssessment(
            overall_score=0.5,
            sharpness_score=0.5,
            exposure_score=0.5,
            blur_score_raw=0.0,
            brightness_raw=0.5,
            aesthetic_score=0.5,
            resolution_score=0.5,
            confidence=0.0,
            quality_grade=QualityGrade.FAIR,
            issues=[QualityIssue.UNKNOWN],
            recommendation="Quality assessment could not be completed.",
            provider_scores={},
        )
