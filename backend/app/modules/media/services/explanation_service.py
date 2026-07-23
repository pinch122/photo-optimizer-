"""
Deterministic explanation generator for PhotoMind AI search matches.

Sprint 7: Integrated with HybridReranker boost_reasons so every explanation
reflects both embedding signals AND AI Memory Record signals.
No LLM is used. All explanations derive from already-stored database values.
"""

from typing import List, Optional
from app.modules.media.models import MediaAsset


class ExplanationService:

    @staticmethod
    def generate_explanation(
        query_text: str,
        asset: MediaAsset,
        score: float,
        boost_reasons: Optional[List[str]] = None,
        confidence_level: Optional[str] = None,
    ) -> List[str]:
        """
        Build a human-readable explanation list for a search result.

        Sources (in priority order):
        1. boost_reasons from HybridReranker & Intent Validation
        2. Duplicate check
        3. Scene & Color signals
        4. Similarity percentage + confidence level
        """
        explanations: List[str] = []
        query_lower = query_text.lower()
        ai = asset.ai_analysis
        similarity_pct = max(0, min(100, int(round(score * 100))))

        # ── 0. Duplicate shortcut ─────────────────────────────────────────────
        if "duplicate" in query_lower:
            return [
                "Perceptual hash is nearly identical",
                f"Visual similarity: {similarity_pct}%",
                "Potential duplicate",
            ]

        # ── 1. Hybrid reranker & Intent boost reasons (Memory Record signals) ──
        seen: set = set()
        for reason in (boost_reasons or []):
            if reason and reason not in seen:
                explanations.append(reason)
                seen.add(reason)
                if len(explanations) >= 4:
                    break

        # ── 2. Embedding signal (if no Memory Record boosted this result) ─────
        if not explanations:
            if similarity_pct >= 85:
                explanations.append("High visual & semantic similarity")
            else:
                explanations.append("Semantic similarity to your search")

        # ── 3. Indoor/Outdoor context ─────────────────────────────────────────
        if len(explanations) < 4 and ai:
            if ai.indoor_outdoor:
                explanations.append(
                    f"{'Indoor' if ai.indoor_outdoor == 'indoor' else 'Outdoor'} scene"
                )
            elif ai.is_indoor is not None:
                explanations.append("Indoor scene" if ai.is_indoor else "Outdoor scene")

        # ── 4. Similarity % + Confidence Level ────────────────────────────────
        explanations.append(f"Similarity: {similarity_pct}%")
        if confidence_level:
            explanations.append(f"Confidence: {confidence_level}")
        elif similarity_pct >= 85:
            explanations.append("Confidence: Very High")
        elif similarity_pct >= 70:
            explanations.append("Confidence: High")
        elif similarity_pct >= 50:
            explanations.append("Confidence: Medium")
        else:
            explanations.append("Confidence: Low")

        return explanations[:6]
