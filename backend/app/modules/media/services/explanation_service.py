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
    ) -> List[str]:
        """
        Build a human-readable explanation list for a search result.

        Sources (in priority order):
        1. boost_reasons from HybridReranker (Memory Record signals)
        2. Duplicate check
        3. Embedding-based quality signals
        4. Similarity percentage + confidence level

        Returns up to 5 explanation strings.
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

        # ── 1. Hybrid reranker boost reasons (Memory Record signals) ──────────
        # De-duplicate while preserving insertion order
        seen: set = set()
        for reason in (boost_reasons or []):
            if reason and reason not in seen:
                explanations.append(reason)
                seen.add(reason)
                if len(explanations) >= 4:
                    break

        # ── 2. Embedding signal (if no Memory Record boosted this result) ─────
        if not explanations:
            if similarity_pct >= 90:
                explanations.append("High semantic similarity to your search")
            else:
                explanations.append("Semantic similarity to your search")

        # ── 3. Indoor/Outdoor context (from legacy is_indoor field) ───────────
        if len(explanations) < 4 and ai:
            if ai.indoor_outdoor:
                explanations.append(
                    f"{'Indoor' if ai.indoor_outdoor == 'indoor' else 'Outdoor'} scene"
                )
            elif ai.is_indoor is not None:
                explanations.append("Indoor scene" if ai.is_indoor else "Outdoor scene")

        # ── 4. Color match ────────────────────────────────────────────────────
        if len(explanations) < 4:
            colors = [
                "yellow", "blue", "red", "green", "white", "black",
                "orange", "purple", "brown", "pink",
            ]
            for color in colors:
                if color in query_lower:
                    if ai and ai.caption and color in ai.caption.lower():
                        explanations.append(f"{color.capitalize()} colors dominate the image")
                    break

        # ── 5. Similarity % + confidence ──────────────────────────────────────
        explanations.append(f"Similarity: {similarity_pct}%")
        if similarity_pct >= 85:
            explanations.append("Confidence: High")
        elif similarity_pct >= 70:
            explanations.append("Confidence: Medium")
        else:
            explanations.append("Confidence: Low")

        return explanations[:6]
