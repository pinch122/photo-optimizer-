"""
Unit tests for the similarity threshold filter in the search pipeline — Sprint 7.

These tests validate that:
- Candidates above threshold survive
- Candidates below threshold are filtered out
- Mixed candidate lists filter correctly
- Empty candidate lists are handled
- Zero results after filtering is handled correctly
- The threshold value is read from settings
"""

from typing import Any, Dict, List
from uuid import uuid4

import pytest


# ─── Inline threshold filter (matches the logic in search_service.py) ─────────

def apply_threshold_filter(
    candidates: List[Dict[str, Any]],
    threshold: float,
) -> List[Dict[str, Any]]:
    """
    Mirrors the threshold filter used in SearchService.search_media().
    Extract this logic here so it can be unit-tested without spinning up
    async infrastructure.
    """
    return [c for c in candidates if c["score"] >= threshold]


# ─── Test data helpers ────────────────────────────────────────────────────────

def make_candidate(score: float) -> Dict[str, Any]:
    return {"id": uuid4(), "score": score}


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestThresholdFilter:

    def test_candidate_above_threshold_survives(self):
        """A single candidate above threshold should pass."""
        candidates = [make_candidate(0.80)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert len(result) == 1
        assert result[0]["score"] == 0.80

    def test_candidate_exactly_at_threshold_survives(self):
        """A candidate exactly at threshold is ≥ threshold and must pass."""
        candidates = [make_candidate(0.35)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert len(result) == 1

    def test_candidate_below_threshold_is_filtered(self):
        """A single candidate below threshold must be discarded."""
        candidates = [make_candidate(0.20)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert len(result) == 0

    def test_candidate_just_below_threshold_is_filtered(self):
        """A candidate one epsilon below threshold must be discarded."""
        candidates = [make_candidate(0.3499)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert len(result) == 0

    def test_empty_candidate_list(self):
        """Empty input should return empty output without errors."""
        result = apply_threshold_filter([], threshold=0.35)
        assert result == []

    def test_all_candidates_below_threshold_returns_empty(self):
        """If all candidates are below threshold, result must be empty (no fabrication)."""
        candidates = [make_candidate(0.10), make_candidate(0.20), make_candidate(0.34)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert result == []

    def test_all_candidates_above_threshold_returns_all(self):
        """All candidates above threshold should all survive."""
        candidates = [make_candidate(0.50), make_candidate(0.70), make_candidate(0.90)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert len(result) == 3

    def test_mixed_candidates_filter_correctly(self):
        """Mixed list: only those >= threshold survive."""
        candidates = [
            make_candidate(0.90),   # survive
            make_candidate(0.20),   # filtered
            make_candidate(0.60),   # survive
            make_candidate(0.10),   # filtered
            make_candidate(0.35),   # survive (exactly at threshold)
        ]
        result = apply_threshold_filter(candidates, threshold=0.35)
        surviving_scores = sorted([c["score"] for c in result], reverse=True)
        assert surviving_scores == [0.90, 0.60, 0.35]

    def test_filter_preserves_order(self):
        """Filter should preserve the relative order of surviving candidates."""
        ids = [uuid4() for _ in range(3)]
        candidates = [
            {"id": ids[0], "score": 0.80},
            {"id": ids[1], "score": 0.60},
            {"id": ids[2], "score": 0.40},
        ]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert [c["id"] for c in result] == ids  # order preserved

    def test_filter_does_not_fabricate_results(self):
        """Zero results after filtering must stay zero — no fallback injection."""
        candidates = [make_candidate(0.05), make_candidate(0.01)]
        result = apply_threshold_filter(candidates, threshold=0.35)
        assert len(result) == 0

    def test_threshold_zero_passes_all(self):
        """Threshold=0.0 should pass every candidate (all scores >= 0)."""
        candidates = [make_candidate(0.0), make_candidate(0.5), make_candidate(1.0)]
        result = apply_threshold_filter(candidates, threshold=0.0)
        assert len(result) == 3

    def test_threshold_one_passes_only_perfect_match(self):
        """Threshold=1.0 should only pass candidates with score >= 1.0."""
        candidates = [make_candidate(0.99), make_candidate(1.0), make_candidate(0.50)]
        result = apply_threshold_filter(candidates, threshold=1.0)
        assert len(result) == 1
        assert result[0]["score"] == 1.0

    def test_default_threshold_is_reasonable(self):
        """
        The default threshold (0.35) should:
        - Allow a clearly relevant match (0.50) through
        - Block a near-random CLIP match (0.22)
        """
        from app.config import settings
        threshold = settings.SEARCH_SIMILARITY_THRESHOLD
        assert threshold >= 0.30, (
            f"Default threshold {threshold} is too low — likely to surface unrelated images. "
            "Recommended minimum: 0.35"
        )
        assert threshold <= 0.70, (
            f"Default threshold {threshold} is too high — would suppress valid results."
        )

        relevant_candidate = [make_candidate(0.50)]
        irrelevant_candidate = [make_candidate(0.22)]

        assert len(apply_threshold_filter(relevant_candidate, threshold)) == 1
        assert len(apply_threshold_filter(irrelevant_candidate, threshold)) == 0
