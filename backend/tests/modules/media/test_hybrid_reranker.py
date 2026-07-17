"""
Unit tests for HybridReranker — Sprint 7.

These tests are fully synchronous and have zero external dependencies.
They create lightweight mock MediaAsset / ImageAIAnalysis objects in memory.
"""

import uuid
from unittest.mock import MagicMock
from typing import List, Dict, Any

import pytest

from app.modules.media.services.hybrid_reranker import (
    HybridReranker,
    HybridWeights,
    _PEOPLE_WORDS,
    _DOCUMENT_WORDS,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_ai(
    caption: str = None,
    objects: list = None,
    keywords: dict = None,
    scene: str = None,
    detected_text: str = None,
    event_type: str = None,
    people_count: int = None,
    document_type: str = None,
    indoor_outdoor: str = None,
):
    ai = MagicMock()
    ai.caption = caption
    ai.objects = objects
    ai.keywords = keywords
    ai.scene = scene
    ai.detected_text = detected_text
    ai.event_type = event_type
    ai.people_count = people_count
    ai.document_type = document_type
    ai.indoor_outdoor = indoor_outdoor
    return ai


def make_asset(ai=None):
    asset = MagicMock()
    asset.ai_analysis = ai
    return asset


def make_candidates(ids_scores: List[tuple]) -> List[Dict[str, Any]]:
    return [{"id": uid, "score": score} for uid, score in ids_scores]


# ─── Tokenizer tests ─────────────────────────────────────────────────────────

def test_tokenizer_basic():
    tokens = HybridReranker._tokenize("dog on the beach")
    assert "dog" in tokens
    assert "beach" in tokens
    assert "on" not in tokens    # stopword
    assert "the" not in tokens   # stopword


def test_tokenizer_strips_punctuation():
    tokens = HybridReranker._tokenize("cat, dog! fish?")
    assert "cat" in tokens
    assert "dog" in tokens
    assert "fish" in tokens


def test_tokenizer_empty():
    assert HybridReranker._tokenize("") == set()
    assert HybridReranker._tokenize(None) == set()


# ─── Individual signal scoring ────────────────────────────────────────────────

def test_caption_score_match():
    ai = make_ai(caption="A group of friends at the beach")
    tokens = HybridReranker._tokenize("group beach")
    score = HybridReranker._score_caption(tokens, ai)
    assert score > 0.0


def test_caption_score_no_match():
    ai = make_ai(caption="A red sports car")
    tokens = HybridReranker._tokenize("beach ocean")
    score = HybridReranker._score_caption(tokens, ai)
    assert score == 0.0


def test_caption_score_none():
    ai = make_ai(caption=None)
    tokens = HybridReranker._tokenize("beach")
    assert HybridReranker._score_caption(tokens, ai) == 0.0


def test_objects_score_match():
    ai = make_ai(objects=["person", "car", "tree"])
    tokens = HybridReranker._tokenize("person standing")
    score = HybridReranker._score_objects(tokens, ai)
    assert score > 0.0


def test_objects_score_no_match():
    ai = make_ai(objects=["tree", "cloud"])
    tokens = HybridReranker._tokenize("dog cat")
    assert HybridReranker._score_objects(tokens, ai) == 0.0


def test_scene_score_match():
    ai = make_ai(scene="beach")
    tokens = HybridReranker._tokenize("beach vacation")
    assert HybridReranker._score_scene(tokens, ai) == 1.0


def test_scene_score_no_match():
    ai = make_ai(scene="mountain")
    tokens = HybridReranker._tokenize("beach ocean")
    assert HybridReranker._score_scene(tokens, ai) == 0.0


def test_ocr_score_match():
    ai = make_ai(detected_text="Total amount: $45.00 receipt")
    tokens = HybridReranker._tokenize("receipt total")
    score = HybridReranker._score_ocr(tokens, ai)
    assert score > 0.0


def test_people_score_no_people():
    ai = make_ai(people_count=0)
    assert HybridReranker._score_people(ai) == 0.0


def test_people_score_one():
    ai = make_ai(people_count=1)
    score = HybridReranker._score_people(ai)
    assert 0.0 < score < 1.0


def test_people_score_many():
    ai = make_ai(people_count=8)
    assert HybridReranker._score_people(ai) == 1.0


def test_document_score_match():
    ai = make_ai(document_type="receipt")
    tokens = HybridReranker._tokenize("receipt payment")
    assert HybridReranker._score_document(tokens, ai) == 1.0


def test_document_score_no_match():
    ai = make_ai(document_type="menu")
    tokens = HybridReranker._tokenize("receipt payment")
    assert HybridReranker._score_document(tokens, ai) == 0.0


# ─── Reranker integration tests ───────────────────────────────────────────────

def test_rerank_empty_candidates():
    result = HybridReranker.rerank([], "beach", {})
    assert result == []


def test_rerank_preserves_all_candidates():
    ids = [uuid.uuid4() for _ in range(3)]
    candidates = make_candidates([(ids[0], 0.8), (ids[1], 0.7), (ids[2], 0.6)])
    assets_map = {uid: make_asset(make_ai(caption="sunset")) for uid in ids}
    result = HybridReranker.rerank(candidates, "sunset", assets_map)
    assert len(result) == 3


def test_rerank_people_query_boosts_image_with_people():
    """An image with people_count=5 should rank above one with people_count=0
    for a 'group photo' query, even if the latter has a slightly higher embedding."""
    uid_people = uuid.uuid4()
    uid_no_people = uuid.uuid4()

    candidates = make_candidates([
        (uid_no_people, 0.80),   # Higher embedding, but no people
        (uid_people, 0.75),      # Slightly lower embedding, but 5 people
    ])
    assets_map = {
        uid_people: make_asset(make_ai(people_count=5, caption="group of friends")),
        uid_no_people: make_asset(make_ai(people_count=0, caption="landscape")),
    }

    result = HybridReranker.rerank(candidates, "group photo", assets_map)
    assert result[0]["id"] == uid_people, "Image with people should rank first"


def test_rerank_receipt_query_boosts_document():
    """An image with document_type=receipt should rank above an unrelated image."""
    uid_receipt = uuid.uuid4()
    uid_other = uuid.uuid4()

    candidates = make_candidates([
        (uid_other, 0.82),
        (uid_receipt, 0.70),
    ])
    assets_map = {
        uid_receipt: make_asset(make_ai(document_type="receipt", caption="store receipt")),
        uid_other: make_asset(make_ai(caption="mountain landscape")),
    }

    result = HybridReranker.rerank(candidates, "receipt", assets_map)
    assert result[0]["id"] == uid_receipt


def test_rerank_beach_query_uses_scene():
    """Image with scene=beach should rank above image with no scene."""
    uid_beach = uuid.uuid4()
    uid_other = uuid.uuid4()

    candidates = make_candidates([
        (uid_other, 0.75),
        (uid_beach, 0.70),
    ])
    assets_map = {
        uid_beach: make_asset(make_ai(scene="beach", caption="ocean waves")),
        uid_other: make_asset(make_ai(scene="office", caption="desk")),
    }

    result = HybridReranker.rerank(candidates, "beach", assets_map)
    assert result[0]["id"] == uid_beach


def test_rerank_adds_hybrid_score_key():
    uid = uuid.uuid4()
    candidates = make_candidates([(uid, 0.75)])
    assets_map = {uid: make_asset(make_ai(caption="dog"))}
    result = HybridReranker.rerank(candidates, "dog", assets_map)
    assert "hybrid_score" in result[0]
    assert 0.0 <= result[0]["hybrid_score"] <= 1.0


def test_rerank_adds_boost_reasons_key():
    uid = uuid.uuid4()
    candidates = make_candidates([(uid, 0.75)])
    assets_map = {uid: make_asset(make_ai(caption="dog at the beach", scene="beach"))}
    result = HybridReranker.rerank(candidates, "beach dog", assets_map)
    assert "boost_reasons" in result[0]
    assert isinstance(result[0]["boost_reasons"], list)


def test_rerank_no_ai_analysis_falls_back_to_embedding():
    """Assets with no AI analysis should still be returned, ranked by embedding."""
    ids = [uuid.uuid4() for _ in range(2)]
    candidates = make_candidates([(ids[0], 0.90), (ids[1], 0.60)])
    assets_map = {uid: make_asset(ai=None) for uid in ids}
    result = HybridReranker.rerank(candidates, "dog", assets_map)
    assert result[0]["id"] == ids[0]   # Higher embedding stays first


def test_weights_from_settings():
    mock_settings = MagicMock()
    mock_settings.HYBRID_WEIGHT_EMBEDDING = 0.6
    mock_settings.HYBRID_WEIGHT_CAPTION = 0.1
    mock_settings.HYBRID_WEIGHT_OBJECTS = 0.1
    mock_settings.HYBRID_WEIGHT_KEYWORDS = 0.05
    mock_settings.HYBRID_WEIGHT_SCENE = 0.05
    mock_settings.HYBRID_WEIGHT_OCR = 0.05
    mock_settings.HYBRID_WEIGHT_EVENT = 0.02
    mock_settings.HYBRID_WEIGHT_PEOPLE = 0.02
    mock_settings.HYBRID_WEIGHT_DOCUMENT = 0.01

    weights = HybridWeights.from_settings(mock_settings)
    assert weights.embedding == 0.6
    assert weights.caption == 0.1
