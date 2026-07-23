"""
Unit tests for the Quality Assessment Engine.

Design principles
-----------------
- All tests use synthetic PIL images generated in-memory — no disk I/O.
- No external services (no DB, no Qdrant, no CLIP network download).
- CLIP-IQA provider is patched out where we need deterministic scores;
  tested separately using a mock model.
- Tests validate behaviour, not implementation details.

Test matrix
-----------
Good daylight image          → EXCELLENT or GOOD grade, no issues
Dark artistic image          → NOT VERY_POOR (artistic dark ≠ poor quality)
Blurry image                 → OUT_OF_FOCUS or MOTION_BLUR issue
Overexposed image            → OVER_EXPOSURE issue
Low-resolution image         → LOW_RESOLUTION issue
Near-black lens obstruction  → LENS_OBSTRUCTION issue
Existing metrics reuse       → ClassicalProvider does not recompute
Custom fusion weights        → overall_score changes predictably
Grade boundaries             → verify all 5 grade thresholds
Issue multi-signal guard     → dark alone does not produce LOW_EXPOSURE
"""

from __future__ import annotations

import math
import numpy as np
import pytest
from PIL import Image, ImageDraw
from unittest.mock import MagicMock, patch

from app.services.quality import (
    QualityAssessment,
    QualityConfig,
    QualityGrade,
    QualityIssue,
    QualityService,
)
from app.services.quality.providers.base_provider import ProviderResult, QualityProvider
from app.services.quality.providers.classical_provider import ClassicalProvider
from app.services.quality.providers.clip_iqa_provider import CLIPIQAProvider


# ─── Image Factories ──────────────────────────────────────────────────────────

def _solid_image(brightness: int, width: int = 400, height: int = 300) -> Image.Image:
    """Solid colour image — minimum texture, controlled brightness."""
    return Image.new("RGB", (width, height), color=(brightness, brightness, brightness))


def _gradient_image(width: int = 800, height: int = 600) -> Image.Image:
    """
    Smooth horizontal gradient with fine vertical stripes to produce
    a well-defined edge structure (sharp, well-exposed mid-tone image).
    """
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for x in range(width):
        # Base gradient (mid-grey ± 60)
        base = 100 + int(120 * x / width)
        for y in range(height):
            # Vertical stripes to add high-frequency edge content
            stripe = 20 if (x % 10 < 5) else 0
            v = min(255, base + stripe)
            pixels[x, y] = (v, v, v)  # type: ignore[index]
    return img


def _blurry_image(width: int = 400, height: int = 300) -> Image.Image:
    """
    Solid mid-grey image — very low edge variance (simulates defocused capture).
    """
    return _solid_image(128, width, height)


def _low_res_image() -> Image.Image:
    """50×40 px — below 0.5 MP threshold."""
    return _gradient_image(50, 40)


def _near_black_image() -> Image.Image:
    """Almost black (brightness=5/255) — lens obstruction territory."""
    return _solid_image(5)


def _overexposed_image() -> Image.Image:
    """Near-white image (brightness=248/255)."""
    return _solid_image(248)


def _dark_but_sharp_image(width: int = 600, height: int = 400) -> Image.Image:
    """
    Dark (brightness ≈ 0.18) but with strong edge content — simulates a
    concert/sunset scene that should NOT be flagged as low quality.
    """
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw light shapes on dark background — produces high edge variance
    for i in range(0, width, 40):
        draw.line([(i, 0), (i, height)], fill=(60, 60, 80), width=2)
    for j in range(0, height, 40):
        draw.line([(0, j), (width, j)], fill=(60, 60, 80), width=2)
    return img


# ─── Mock Provider Helper ─────────────────────────────────────────────────────

class FixedProvider(QualityProvider):
    """Provider that always returns a fixed ProviderResult — for unit testing fusion."""

    def __init__(self, name_str: str, **scores):
        self._name = name_str
        self._scores = scores

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "1.0"

    def evaluate(self, image, existing_metrics=None) -> ProviderResult:
        return ProviderResult(
            is_available=self._scores.get("is_available", True),
            sharpness_score=self._scores.get("sharpness_score", 0.5),
            exposure_score=self._scores.get("exposure_score", 0.5),
            resolution_score=self._scores.get("resolution_score", 0.5),
            aesthetic_score=self._scores.get("aesthetic_score", 0.5),
            confidence=self._scores.get("confidence", 1.0),
            raw_metrics=self._scores.get("raw_metrics", {}),
        )


# ─── Classical Provider Tests ─────────────────────────────────────────────────

class TestClassicalProvider:

    def test_good_image_returns_high_scores(self):
        img = _gradient_image()
        provider = ClassicalProvider()
        result = provider.evaluate(img)
        assert result.confidence == 1.0
        assert result.sharpness_score > 0.5, "Gradient image should be rated sharp"
        assert 0.3 < result.exposure_score < 0.9, "Mid-tone gradient should have decent exposure"
        assert result.resolution_score > 0.0

    def test_blurry_solid_image_returns_low_sharpness(self):
        img = _blurry_image()
        provider = ClassicalProvider()
        result = provider.evaluate(img)
        assert result.sharpness_score < 0.5, "Solid image has no edges — should be rated unsharp"

    def test_low_resolution_detected(self):
        img = _low_res_image()
        provider = ClassicalProvider()
        result = provider.evaluate(img)
        assert result.resolution_score < 0.1, "50×40 should be very low resolution score"

    def test_overexposed_image_poor_exposure_score(self):
        img = _overexposed_image()
        provider = ClassicalProvider()
        result = provider.evaluate(img)
        # Near-white → brightness ≈ 0.97 → bell curve → near 0
        assert result.exposure_score < 0.25

    def test_dark_image_poor_exposure_score(self):
        img = _solid_image(25)  # brightness ≈ 0.10
        provider = ClassicalProvider()
        result = provider.evaluate(img)
        assert result.exposure_score < 0.40

    def test_existing_metrics_reused(self):
        """ClassicalProvider must not recompute brightness when already provided."""
        img = _gradient_image()  # naturally mid-tone
        provider = ClassicalProvider()

        # Inject a brightness value that is very different from the actual image
        injected_brightness = 0.99   # overexposed sentinel
        result = provider.evaluate(img, existing_metrics={"brightness": injected_brightness})

        assert result.raw_metrics.get("brightness_source") == 0.0, (
            "brightness_source==0 means reused; source==1 means recomputed"
        )
        assert abs(result.raw_metrics["brightness"] - injected_brightness) < 0.01

    def test_existing_sharpness_reused(self):
        img = _gradient_image()
        provider = ClassicalProvider()
        injected_sharpness = 5.0   # low value → should produce low sharpness_score
        result = provider.evaluate(img, existing_metrics={"sharpness": injected_sharpness})
        assert result.raw_metrics.get("sharpness_source") == 0.0
        # 5.0 edge_stddev → sigmoid → should be below 0.5
        assert result.sharpness_score < 0.5


# ─── CLIP-IQA Provider Tests ──────────────────────────────────────────────────

class TestCLIPIQAProvider:

    def test_graceful_fallback_when_clip_unavailable(self):
        """When EmbeddingService.get_model() fails, return is_available=False, confidence=0, aesthetic_score=None."""
        provider = CLIPIQAProvider()
        img = _gradient_image()

        with patch(
            "app.modules.media.services.embedding_service.EmbeddingService.get_model",
            side_effect=RuntimeError("mock: model not available"),
        ):
            result = provider.evaluate(img)

        assert result.is_available is False
        assert result.confidence == 0.0
        assert result.aesthetic_score is None   # No fabricated scores!

    def test_clip_iqa_with_mock_model(self):
        """CLIP-IQA computes aesthetic_score using prompt-pair softmax probability."""
        provider = CLIPIQAProvider()
        img = _gradient_image()

        mock_model = MagicMock()
        dim = 512
        img_vec = np.zeros(dim, dtype=np.float32)
        img_vec[0] = 1.0  # unit vector in dimension 0

        pos_vec = np.zeros(dim, dtype=np.float32)
        pos_vec[0] = 1.0  # aligned with image

        neg_vec = np.zeros(dim, dtype=np.float32)
        neg_vec[1] = 1.0  # orthogonal to image

        def mock_encode(input_, normalize_embeddings=True, **kwargs):
            if isinstance(input_, Image.Image):
                return img_vec
            if isinstance(input_, str) and ("high quality" in input_ or "clean" in input_ or "beautiful" in input_):
                return pos_vec
            return neg_vec

        mock_model.encode = mock_encode

        with patch(
            "app.modules.media.services.embedding_service.EmbeddingService.get_model",
            return_value=mock_model,
        ):
            result = provider.evaluate(img)

        assert result.is_available is True
        assert result.confidence == 1.0
        assert result.aesthetic_score is not None
        assert result.aesthetic_score > 0.9, f"Expected high aesthetic score, got {result.aesthetic_score}"


# ─── QualityService / Fusion Tests ───────────────────────────────────────────

class TestQualityServiceFusion:

    def test_default_factory_initialises(self):
        service = QualityService.default()
        assert len(service._providers) == 2

    def test_no_providers_raises(self):
        with pytest.raises(ValueError, match="at least one provider"):
            QualityService(providers=[])

    def test_fusion_weights_sum_validated(self):
        bad_config = QualityConfig(
            weight_sharpness=0.5,
            weight_exposure=0.5,
            weight_aesthetic=0.5,
            weight_resolution=0.5,
        )
        with pytest.raises(ValueError, match="sum to 1.0"):
            QualityService(providers=[ClassicalProvider()], config=bad_config)

    def test_fixed_providers_produce_expected_overall(self):
        """Fusion arithmetic: verify weighted average is computed correctly."""
        cfg = QualityConfig(
            weight_sharpness=0.35,
            weight_exposure=0.30,
            weight_aesthetic=0.25,
            weight_resolution=0.10,
        )
        # Single fixed provider with known scores
        provider = FixedProvider(
            "fixed",
            sharpness_score=0.8,
            exposure_score=0.7,
            aesthetic_score=0.6,
            resolution_score=1.0,
            confidence=1.0,
            raw_metrics={"brightness": 0.5, "blur_score": 10.0},
        )
        service = QualityService(providers=[provider], config=cfg)
        result = service.evaluate(_gradient_image())

        expected = (0.35 * 0.8) + (0.30 * 0.7) + (0.25 * 0.6) + (0.10 * 1.0)
        assert abs(result.overall_score - expected) < 0.01

    def test_custom_weights_change_score(self):
        """Increasing weight_sharpness while keeping sharpness low should lower overall."""
        high_sharpness_cfg = QualityConfig(
            weight_sharpness=0.70,
            weight_exposure=0.10,
            weight_aesthetic=0.10,
            weight_resolution=0.10,
        )
        low_sharpness_cfg = QualityConfig(
            weight_sharpness=0.10,
            weight_exposure=0.30,
            weight_aesthetic=0.30,
            weight_resolution=0.30,
        )
        provider = FixedProvider(
            "p",
            sharpness_score=0.1,   # very low sharpness
            exposure_score=0.9,
            aesthetic_score=0.9,
            resolution_score=0.9,
            confidence=1.0,
            raw_metrics={"brightness": 0.5, "blur_score": 10.0},
        )
        img = _gradient_image()
        high_result = QualityService(providers=[provider], config=high_sharpness_cfg).evaluate(img)
        low_result  = QualityService(providers=[provider], config=low_sharpness_cfg).evaluate(img)
        assert high_result.overall_score < low_result.overall_score

    def test_zero_confidence_provider_excluded_from_aesthetic(self):
        """A provider with confidence=0 should not push aesthetic score away from neutral."""
        confident_p = FixedProvider(
            "confident",
            sharpness_score=0.8, exposure_score=0.8,
            aesthetic_score=0.8, resolution_score=0.8,
            confidence=1.0,
            raw_metrics={"brightness": 0.5, "blur_score": 5.0},
        )
        zero_p = FixedProvider(
            "zero_conf",
            sharpness_score=0.0, exposure_score=0.0,
            aesthetic_score=0.0, resolution_score=0.0,
            confidence=0.0,
            raw_metrics={},
        )
        service = QualityService(providers=[confident_p, zero_p])
        result = service.evaluate(_gradient_image())
        # Weighted mean of [0.8, 0.0] with weights [1.0, 0.0] → 0.8
        assert result.aesthetic_score > 0.7


# ─── Grade Boundary Tests ─────────────────────────────────────────────────────

class TestGradeBoundaries:

    @pytest.mark.parametrize("score, expected_grade", [
        (0.90, QualityGrade.EXCELLENT),
        (0.85, QualityGrade.EXCELLENT),
        (0.84, QualityGrade.GOOD),
        (0.70, QualityGrade.GOOD),
        (0.69, QualityGrade.FAIR),
        (0.50, QualityGrade.FAIR),
        (0.49, QualityGrade.POOR),
        (0.30, QualityGrade.POOR),
        (0.29, QualityGrade.VERY_POOR),
        (0.00, QualityGrade.VERY_POOR),
    ])
    def test_grade_thresholds(self, score: float, expected_grade: QualityGrade):
        assert QualityService._assign_grade(score) == expected_grade


# ─── Issue Detection Tests ────────────────────────────────────────────────────

class TestIssueDetection:

    def _service_with_fixed(self, **scores) -> QualityService:
        p = FixedProvider("p", **scores, raw_metrics={"brightness": scores.get("brightness_raw", 0.5), "blur_score": scores.get("blur_score_raw", 10.0)})
        return QualityService(providers=[p])

    def test_good_image_has_no_issues(self):
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.85, exposure_score=0.85,
                aesthetic_score=0.85, resolution_score=0.85,
                confidence=1.0,
                raw_metrics={"brightness": 0.5, "blur_score": 5.0},
            )]
        )
        result = service.evaluate(_gradient_image())
        assert result.issues == []

    def test_blur_detected_with_low_sharpness(self):
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.1, exposure_score=0.7,
                aesthetic_score=0.5, resolution_score=0.8,
                confidence=1.0,
                raw_metrics={"brightness": 0.5, "blur_score": 80.0},
            )]
        )
        result = service.evaluate(_blurry_image())
        assert QualityIssue.MOTION_BLUR in result.issues or QualityIssue.OUT_OF_FOCUS in result.issues

    def test_out_of_focus_without_motion_blur(self):
        """Low sharpness + low blur_raw → out of focus (not motion blur)."""
        cfg = QualityConfig(
            weight_sharpness=0.35, weight_exposure=0.30,
            weight_aesthetic=0.25, weight_resolution=0.10,
            blur_threshold_very_blurry=60.0,
        )
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.1, exposure_score=0.7,
                aesthetic_score=0.5, resolution_score=0.8,
                confidence=1.0,
                raw_metrics={"brightness": 0.5, "blur_score": 20.0},  # below very_blurry
            )],
            config=cfg,
        )
        result = service.evaluate(_blurry_image())
        assert QualityIssue.OUT_OF_FOCUS in result.issues
        assert QualityIssue.MOTION_BLUR not in result.issues

    def test_overexposure_detected(self):
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.7, exposure_score=0.15,
                aesthetic_score=0.4, resolution_score=0.8,
                confidence=1.0,
                raw_metrics={"brightness": 0.95, "blur_score": 5.0},
            )]
        )
        result = service.evaluate(_overexposed_image())
        assert QualityIssue.OVER_EXPOSURE in result.issues

    def test_low_resolution_detected(self):
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.7, exposure_score=0.7,
                aesthetic_score=0.7, resolution_score=0.01,
                confidence=1.0,
                raw_metrics={"brightness": 0.5, "blur_score": 5.0},
            )]
        )
        result = service.evaluate(_low_res_image())
        assert QualityIssue.LOW_RESOLUTION in result.issues

    def test_lens_obstruction_detected(self):
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.05, exposure_score=0.01,
                aesthetic_score=0.1, resolution_score=0.5,
                confidence=1.0,
                raw_metrics={"brightness": 0.02, "blur_score": 90.0},
            )]
        )
        result = service.evaluate(_near_black_image())
        assert QualityIssue.LENS_OBSTRUCTION in result.issues

    def test_dark_alone_does_not_trigger_low_exposure(self):
        """
        CRITICAL: A dark image with high aesthetic score (concert, sunset)
        must NOT be flagged as LOW_EXPOSURE.

        LOW_EXPOSURE requires BOTH:
            brightness < threshold  AND  aesthetic_score < 0.45
        """
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.75, exposure_score=0.3,
                aesthetic_score=0.75,   # high — looks intentionally good
                resolution_score=0.8,
                confidence=1.0,
                raw_metrics={"brightness": 0.12, "blur_score": 8.0},
            )]
        )
        result = service.evaluate(_dark_but_sharp_image())
        assert QualityIssue.LOW_EXPOSURE not in result.issues, (
            "Dark artistic image with good aesthetic should NOT be flagged as LOW_EXPOSURE"
        )

    def test_dark_artistic_image_not_very_poor(self):
        """
        A night/concert/sunset photo — dark but intentionally composed —
        must not receive VERY_POOR grade.
        """
        service = QualityService(
            providers=[FixedProvider(
                "p",
                sharpness_score=0.75, exposure_score=0.35,
                aesthetic_score=0.80, resolution_score=0.85,
                confidence=1.0,
                raw_metrics={"brightness": 0.12, "blur_score": 8.0},
            )]
        )
        result = service.evaluate(_dark_but_sharp_image())
        assert result.quality_grade != QualityGrade.VERY_POOR, (
            f"Dark artistic image should not be VERY_POOR, got {result.quality_grade}"
        )


# ─── End-to-End Classical Integration ────────────────────────────────────────

class TestEndToEndClassical:
    """
    Integration tests using the real ClassicalProvider (no CLIP — deterministic).
    These verify the full pipeline without mocking the provider.
    """

    def test_gradient_image_is_at_least_fair(self):
        """A well-exposed gradient image should score FAIR or above."""
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_gradient_image())
        assert result.quality_grade not in (QualityGrade.POOR, QualityGrade.VERY_POOR)

    def test_blurry_solid_image_has_focus_issue(self):
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_blurry_image())
        has_blur_issue = (
            QualityIssue.OUT_OF_FOCUS in result.issues
            or QualityIssue.MOTION_BLUR in result.issues
        )
        assert has_blur_issue

    def test_overexposed_has_over_exposure_issue(self):
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_overexposed_image())
        assert QualityIssue.OVER_EXPOSURE in result.issues

    def test_near_black_has_lens_obstruction(self):
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_near_black_image())
        assert QualityIssue.LENS_OBSTRUCTION in result.issues

    def test_low_res_has_low_resolution_issue(self):
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_low_res_image())
        assert QualityIssue.LOW_RESOLUTION in result.issues

    def test_assessment_fields_in_range(self):
        """All numeric scores must be in [0.0, 1.0]."""
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_gradient_image())
        for field_name, val in [
            ("overall_score",    result.overall_score),
            ("sharpness_score",  result.sharpness_score),
            ("exposure_score",   result.exposure_score),
            ("aesthetic_score",  result.aesthetic_score),
            ("resolution_score", result.resolution_score),
            ("confidence",       result.confidence),
        ]:
            assert 0.0 <= val <= 1.0, f"{field_name} out of range: {val}"

    def test_recommendation_string_populated(self):
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_gradient_image())
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0

    def test_provider_scores_dict_populated(self):
        service = QualityService(providers=[ClassicalProvider()])
        result = service.evaluate(_gradient_image())
        assert "classical_cv" in result.provider_scores
        assert "brightness" in result.provider_scores["classical_cv"]
