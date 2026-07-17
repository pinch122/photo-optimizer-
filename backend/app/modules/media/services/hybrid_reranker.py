"""
Hybrid Search Reranker — Sprint 7.

A pure, dependency-free reranking engine that combines CLIP embedding similarity
with AI Memory Record signals to produce more intuitive search rankings.

Architecture
------------
This module is intentionally isolated:
  - No DB calls
  - No async
  - No external imports beyond stdlib
  - Fully unit-testable without any FastAPI/SQLAlchemy fixtures

Usage
-----
    from app.modules.media.services.hybrid_reranker import HybridReranker

    reranked = HybridReranker.rerank(
        candidates=filtered_candidates,   # [{"id": UUID, "score": float}, ...]
        query_text="group photo at beach",
        assets_map={uuid: MediaAsset},    # already loaded with .ai_analysis
        weights=HybridWeights(),
    )
    # Returns same list, re-sorted by hybrid_score, with "hybrid_score" key added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import UUID


# ─── Stop-word filter ─────────────────────────────────────────────────────────
# Short, common words that carry no semantic signal for image search
_STOPWORDS: Set[str] = {
    "a", "an", "the", "is", "in", "on", "at", "of", "for", "to", "and",
    "or", "with", "my", "me", "i", "this", "that", "photo", "picture",
    "image", "photos", "pictures", "images", "show", "give", "find",
}

# Words that indicate "people-related" queries
_PEOPLE_WORDS: Set[str] = {
    "people", "person", "group", "crowd", "family", "friends", "team",
    "couple", "man", "woman", "child", "children", "baby", "faces",
    "portrait", "selfie",
}

# Words that indicate "document-related" queries
_DOCUMENT_WORDS: Set[str] = {
    "receipt", "invoice", "passport", "id", "card", "ticket", "certificate",
    "document", "letter", "menu", "whiteboard", "poster", "screenshot",
    "text", "ocr", "scan", "scanned",
}


@dataclass
class HybridWeights:
    """
    Scoring weights for each signal in the hybrid reranker.

    All weights are floats in [0, 1]. They do not need to sum to exactly 1.0 —
    the final hybrid score is a weighted sum clamped to [0, 1].

    Construct from app settings:
        HybridWeights.from_settings(settings)
    """
    embedding: float = 0.55
    caption: float = 0.15
    objects: float = 0.10
    keywords: float = 0.08
    scene: float = 0.06
    ocr: float = 0.05
    event: float = 0.03
    people: float = 0.03
    document: float = 0.03

    @classmethod
    def from_settings(cls, settings: Any) -> "HybridWeights":
        """Construct weights from the app Settings instance."""
        return cls(
            embedding=settings.HYBRID_WEIGHT_EMBEDDING,
            caption=settings.HYBRID_WEIGHT_CAPTION,
            objects=settings.HYBRID_WEIGHT_OBJECTS,
            keywords=settings.HYBRID_WEIGHT_KEYWORDS,
            scene=settings.HYBRID_WEIGHT_SCENE,
            ocr=settings.HYBRID_WEIGHT_OCR,
            event=settings.HYBRID_WEIGHT_EVENT,
            people=settings.HYBRID_WEIGHT_PEOPLE,
            document=settings.HYBRID_WEIGHT_DOCUMENT,
        )


@dataclass
class ScoredCandidate:
    """Holds all computed sub-scores for a single candidate."""
    asset_id: UUID
    embedding_score: float
    caption_score: float = 0.0
    objects_score: float = 0.0
    keywords_score: float = 0.0
    scene_score: float = 0.0
    ocr_score: float = 0.0
    event_score: float = 0.0
    people_score: float = 0.0
    document_score: float = 0.0
    hybrid_score: float = 0.0
    boost_reasons: List[str] = field(default_factory=list)


class HybridReranker:
    """
    Stateless reranker. All methods are class-level — no instantiation needed.
    """

    @classmethod
    def rerank(
        cls,
        candidates: List[Dict[str, Any]],
        query_text: str,
        assets_map: Dict[UUID, Any],
        weights: Optional[HybridWeights] = None,
    ) -> List[Dict[str, Any]]:
        """
        Re-sort candidates by hybrid score using AI Memory Record signals.

        Parameters
        ----------
        candidates : list of {"id": UUID, "score": float, ...}
            Threshold-filtered Qdrant candidates (embedding score already applied).
        query_text : str
            The raw user query string.
        assets_map : dict[UUID, MediaAsset]
            Already-loaded MediaAsset objects keyed by ID. Each asset must have
            .ai_analysis eagerly loaded (or None).
        weights : HybridWeights, optional
            Scoring weights. Defaults to HybridWeights() (built-in defaults).

        Returns
        -------
        list of candidates sorted by hybrid_score descending.
        Each dict gains a "hybrid_score" key and a "boost_reasons" list.
        """
        if not candidates:
            return candidates

        if weights is None:
            weights = HybridWeights()

        query_tokens = cls._tokenize(query_text)
        is_people_query = bool(query_tokens & _PEOPLE_WORDS)
        is_document_query = bool(query_tokens & _DOCUMENT_WORDS)

        scored: List[ScoredCandidate] = []

        for hit in candidates:
            asset_id = hit["id"]
            embedding_score = float(hit.get("score", 0.0))
            asset = assets_map.get(asset_id)
            ai = asset.ai_analysis if asset else None

            sc = ScoredCandidate(
                asset_id=asset_id,
                embedding_score=embedding_score,
            )

            if ai:
                sc.caption_score = cls._score_caption(query_tokens, ai)
                sc.objects_score = cls._score_objects(query_tokens, ai)
                sc.keywords_score = cls._score_keywords(query_tokens, ai)
                sc.scene_score = cls._score_scene(query_tokens, ai)
                sc.ocr_score = cls._score_ocr(query_tokens, ai)
                sc.event_score = cls._score_event(query_tokens, ai)

                if is_people_query:
                    sc.people_score = cls._score_people(ai)
                if is_document_query:
                    sc.document_score = cls._score_document(query_tokens, ai)

                sc.boost_reasons = cls._collect_boost_reasons(
                    query_tokens, ai, sc, is_people_query, is_document_query
                )

            sc.hybrid_score = cls._compute_hybrid_score(sc, weights)
            scored.append(sc)

        # Sort by hybrid score descending
        scored.sort(key=lambda s: s.hybrid_score, reverse=True)

        # Rebuild output dicts preserving original keys + adding hybrid data
        scored_map = {s.asset_id: s for s in scored}
        result = []
        for sc in scored:
            hit = next(h for h in candidates if h["id"] == sc.asset_id)
            out = dict(hit)
            out["hybrid_score"] = sc.hybrid_score
            out["boost_reasons"] = sc.boost_reasons
            result.append(out)

        return result

    # ─── Scoring helpers ──────────────────────────────────────────────────────

    @classmethod
    def _compute_hybrid_score(cls, sc: ScoredCandidate, w: HybridWeights) -> float:
        score = (
            w.embedding  * sc.embedding_score  +
            w.caption    * sc.caption_score     +
            w.objects    * sc.objects_score     +
            w.keywords   * sc.keywords_score    +
            w.scene      * sc.scene_score       +
            w.ocr        * sc.ocr_score         +
            w.event      * sc.event_score       +
            w.people     * sc.people_score      +
            w.document   * sc.document_score
        )
        return round(min(1.0, max(0.0, score)), 6)

    @classmethod
    def _score_caption(cls, query_tokens: Set[str], ai: Any) -> float:
        """1.0 if any query token appears in the caption, else 0.0."""
        if not ai.caption:
            return 0.0
        caption_tokens = cls._tokenize(ai.caption)
        matched = query_tokens & caption_tokens
        if not matched:
            return 0.0
        # Partial credit proportional to fraction of query words matched
        return min(1.0, len(matched) / max(1, len(query_tokens)))

    @classmethod
    def _score_objects(cls, query_tokens: Set[str], ai: Any) -> float:
        """Proportion of query tokens that match detected objects."""
        if not ai.objects:
            return 0.0
        obj_tokens: Set[str] = set()
        for obj in ai.objects:
            obj_tokens |= cls._tokenize(obj)
        matched = query_tokens & obj_tokens
        if not matched:
            return 0.0
        return min(1.0, len(matched) / max(1, len(query_tokens)))

    @classmethod
    def _score_keywords(cls, query_tokens: Set[str], ai: Any) -> float:
        """Match against semantic keyword tags stored in ai.keywords.tags."""
        if not ai.keywords:
            return 0.0
        tags = ai.keywords.get("tags", []) if isinstance(ai.keywords, dict) else []
        if not tags:
            return 0.0
        tag_tokens: Set[str] = set()
        for tag in tags:
            tag_tokens |= cls._tokenize(tag)
        matched = query_tokens & tag_tokens
        if not matched:
            return 0.0
        return min(1.0, len(matched) / max(1, len(query_tokens)))

    @classmethod
    def _score_scene(cls, query_tokens: Set[str], ai: Any) -> float:
        """1.0 if any query token matches the scene label."""
        if not ai.scene:
            return 0.0
        scene_tokens = cls._tokenize(ai.scene)
        return 1.0 if (query_tokens & scene_tokens) else 0.0

    @classmethod
    def _score_ocr(cls, query_tokens: Set[str], ai: Any) -> float:
        """1.0 if any query token appears in detected_text."""
        if not ai.detected_text:
            return 0.0
        ocr_tokens = cls._tokenize(ai.detected_text)
        matched = query_tokens & ocr_tokens
        if not matched:
            return 0.0
        return min(1.0, len(matched) / max(1, len(query_tokens)))

    @classmethod
    def _score_event(cls, query_tokens: Set[str], ai: Any) -> float:
        """1.0 if any query token matches the event_type."""
        if not ai.event_type:
            return 0.0
        event_tokens = cls._tokenize(ai.event_type.replace("_", " "))
        return 1.0 if (query_tokens & event_tokens) else 0.0

    @classmethod
    def _score_people(cls, ai: Any) -> float:
        """Graduated boost based on people_count when query is people-related."""
        if ai.people_count is None:
            return 0.0
        count = ai.people_count
        if count == 0:
            return 0.0
        if count == 1:
            return 0.3
        if count <= 3:
            return 0.6
        return 1.0  # 4+ people → full boost

    @classmethod
    def _score_document(cls, query_tokens: Set[str], ai: Any) -> float:
        """1.0 if document_type matches query, 0.5 if OCR contains doc-related terms."""
        if ai.document_type:
            doc_tokens = cls._tokenize(ai.document_type.replace("_", " "))
            if query_tokens & doc_tokens:
                return 1.0
        return 0.0

    # ─── Explanation collector ─────────────────────────────────────────────────

    @classmethod
    def _collect_boost_reasons(
        cls,
        query_tokens: Set[str],
        ai: Any,
        sc: ScoredCandidate,
        is_people_query: bool,
        is_document_query: bool,
    ) -> List[str]:
        """Produce human-readable boost reasons for the explanation UI."""
        reasons: List[str] = []

        if sc.caption_score > 0 and ai.caption:
            matched = query_tokens & cls._tokenize(ai.caption)
            sample = ", ".join(f'"{w}"' for w in sorted(matched)[:2])
            reasons.append(f"Caption mentions {sample}")

        if sc.objects_score > 0 and ai.objects:
            obj_tokens: Set[str] = set()
            for obj in ai.objects:
                obj_tokens |= cls._tokenize(obj)
            matched = query_tokens & obj_tokens
            sample = ", ".join(sorted(matched)[:2])
            reasons.append(f"Objects include {sample}")

        if sc.scene_score > 0 and ai.scene:
            reasons.append(f"Scene matched: {ai.scene}")

        if sc.keywords_score > 0 and ai.keywords:
            tags = ai.keywords.get("tags", []) if isinstance(ai.keywords, dict) else []
            tag_tokens: Set[str] = set()
            for t in tags:
                tag_tokens |= cls._tokenize(t)
            matched = query_tokens & tag_tokens
            sample = ", ".join(sorted(matched)[:3])
            reasons.append(f"Keywords: {sample}")

        if sc.ocr_score > 0 and ai.detected_text:
            matched = query_tokens & cls._tokenize(ai.detected_text)
            sample = ", ".join(f'"{w}"' for w in sorted(matched)[:2])
            reasons.append(f"OCR text matched {sample}")

        if sc.event_score > 0 and ai.event_type:
            reasons.append(f"Event: {ai.event_type.replace('_', ' ')}")

        if is_people_query and sc.people_score > 0 and ai.people_count:
            reasons.append(f"People detected: {ai.people_count}")

        if is_document_query and sc.document_score > 0 and ai.document_type:
            reasons.append(f"Document type: {ai.document_type.replace('_', ' ')}")

        return reasons

    # ─── Tokenizer ────────────────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """
        Lowercase, strip punctuation, split on whitespace, remove stopwords.
        Returns a set of meaningful tokens.
        """
        if not text:
            return set()
        # Lowercase and replace non-alpha with space
        cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        tokens = {w for w in cleaned.split() if len(w) >= 2 and w not in _STOPWORDS}
        return tokens
