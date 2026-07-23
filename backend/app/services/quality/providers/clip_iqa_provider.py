"""
CLIP-IQA quality provider.

Implements the official CLIP-IQA algorithm (Wang et al., 2022: "CLIP-IQA: Using CLIP
for Unsupervised Image Quality Assessment").

Algorithm:
1. Evaluates antonym prompt pairs (e.g. ("a high quality photo", "a low quality photo")).
2. Computes logit similarities between image embedding and prompt pair embeddings.
3. Applies softmax with temperature scaling (τ = 0.1) to obtain probability P(positive_prompt).
4. Averages probabilities across antonym prompt pairs to compute perceptual aesthetic score.

Model reuse:
Reuses the existing clip-ViT-B-32 singleton instance from EmbeddingService — zero
additional model downloads or VRAM overhead.

Availability and Fallback:
If CLIP model weights are unavailable or inference fails, the provider marks itself as
is_available=False with confidence=0.0 and returns None for all score fields (NO fabricated
dummy scores like 0.5).
"""

from __future__ import annotations

import math
import logging
from typing import Dict, List, Tuple, Optional

import numpy as np
from PIL import Image

from .base_provider import ProviderResult, QualityProvider

logger = logging.getLogger("photomind")

# Temperature scaling parameter for CLIP-IQA logit softmax
_TEMPERATURE_TAU: float = 0.1

# Antonym prompt pairs (positive_prompt, negative_prompt)
_QUALITY_ANTONYM_PAIRS: List[Tuple[str, str]] = [
    ("a high quality photo", "a low quality photo"),
    ("a clear, clean photograph", "a blurry, distorted photograph"),
    ("a beautiful, well-composed photo", "an unappealing, poor photo"),
]


def _pair_softmax_probability(
    img_emb: np.ndarray,
    pos_emb: np.ndarray,
    neg_emb: np.ndarray,
    tau: float = _TEMPERATURE_TAU,
) -> float:
    """
    Computes softmax probability P(positive_prompt) for an antonym prompt pair
    given unit-normalised embeddings.
    """
    pos_sim = float(np.dot(img_emb, pos_emb))
    neg_sim = float(np.dot(img_emb, neg_emb))

    max_sim = max(pos_sim, neg_sim)
    exp_pos = math.exp((pos_sim - max_sim) / tau)
    exp_neg = math.exp((neg_sim - max_sim) / tau)

    return exp_pos / (exp_pos + exp_neg)


class CLIPIQAProvider(QualityProvider):
    """
    Perceptual quality provider using true CLIP-IQA antonym prompt-pair softmax scoring.

    Thread-safe: model access goes through EmbeddingService singleton protected by Lock.
    """

    @property
    def name(self) -> str:
        return "clip_iqa"

    @property
    def version(self) -> str:
        return "1.0"

    def evaluate(
        self,
        image: Image.Image,
        existing_metrics: Optional[Dict[str, float]] = None,
    ) -> ProviderResult:
        try:
            from app.modules.media.services.embedding_service import EmbeddingService

            model = EmbeddingService.get_model()

            img_rgb = image.convert("RGB")
            img_embedding: np.ndarray = model.encode(
                img_rgb, normalize_embeddings=True
            )

            pair_probabilities: List[float] = []
            pair_details: Dict[str, float] = {}

            for pos_text, neg_text in _QUALITY_ANTONYM_PAIRS:
                pos_emb = model.encode(pos_text, normalize_embeddings=True)
                neg_emb = model.encode(neg_text, normalize_embeddings=True)

                prob = _pair_softmax_probability(img_embedding, pos_emb, neg_emb)
                pair_probabilities.append(prob)
                pair_details[f"{pos_text} vs {neg_text}"] = round(prob, 4)

            aesthetic_score = float(np.mean(pair_probabilities))

            return ProviderResult(
                is_available=True,
                sharpness_score=None,    # CLIPIQAProvider only measures perceptual aesthetic score
                exposure_score=None,
                resolution_score=None,
                aesthetic_score=round(aesthetic_score, 4),
                confidence=1.0,
                raw_metrics={
                    "pair_probabilities": pair_details,
                    "mean_aesthetic_prob": round(aesthetic_score, 4),
                },
            )

        except Exception as exc:
            logger.warning(
                f"CLIPIQAProvider: CLIP model unavailable or inference failed: {exc}. "
                "Provider marked unavailable without returning fabricated scores."
            )
            return ProviderResult(
                is_available=False,
                confidence=0.0,
                sharpness_score=None,
                exposure_score=None,
                resolution_score=None,
                aesthetic_score=None,
                raw_metrics={"available": False, "error": str(exc)},
            )
