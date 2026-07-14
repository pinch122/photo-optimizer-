"""
Unit tests for Prompt Engineering, JSON Schema, parsing, and normalization rules.
"""

from __future__ import annotations

import json
import pytest
from app.modules.media.services.ai_analysis.knowledge_schema import (
    KNOWLEDGE_RECORD_JSON_SCHEMA,
    DocumentType,
    EventType,
    IndoorOutdoor,
    Mood,
    SceneType,
    Season,
    Weather,
)
from app.modules.media.services.ai_analysis.prompt_template import (
    build_analysis_prompt,
    get_system_prompt,
)
from app.modules.media.services.ai_analysis.response_parser import (
    KnowledgeRecordParseError,
    parse_knowledge_record,
)


# ─── 1. Schema Tests ─────────────────────────────────────────────────────────

def test_schema_is_valid_json():
    """Verify that the JSON schema is serializeable to JSON and is a dict."""
    assert isinstance(KNOWLEDGE_RECORD_JSON_SCHEMA, dict)
    schema_str = json.dumps(KNOWLEDGE_RECORD_JSON_SCHEMA)
    loaded = json.loads(schema_str)
    assert loaded["title"] == "ImageAIAnalysisRecord"


def test_schema_enums_match_python_enums():
    """Verify the enums defined in JSON schema match the values defined in Python Enum classes."""
    props = KNOWLEDGE_RECORD_JSON_SCHEMA["properties"]

    assert props["scene"]["enum"] == [s.value for s in SceneType] + [None]
    assert props["indoor_outdoor"]["enum"] == [io.value for io in IndoorOutdoor] + [None]
    assert props["weather"]["enum"] == [w.value for w in Weather] + [None]
    assert props["season"]["enum"] == [s.value for s in Season] + [None]
    assert props["document_type"]["enum"] == [d.value for d in DocumentType] + [None]
    assert props["event_type"]["enum"] == [e.value for e in EventType] + [None]
    assert props["mood"]["enum"] == [m.value for m in Mood] + [None]


def test_schema_rules_and_restrictions():
    """Verify schema specifies key restrictions like additionalProperties and required fields."""
    assert KNOWLEDGE_RECORD_JSON_SCHEMA["additionalProperties"] is False
    assert len(KNOWLEDGE_RECORD_JSON_SCHEMA["required"]) > 10
    assert "caption" in KNOWLEDGE_RECORD_JSON_SCHEMA["required"]
    assert "detailed_description" in KNOWLEDGE_RECORD_JSON_SCHEMA["required"]


# ─── 2. Prompt Template Tests ───────────────────────────────────────────────

def test_system_prompt_contains_crucial_instructions():
    """Verify that get_system_prompt contains clear format instructions for the vision model."""
    prompt = get_system_prompt()
    assert "ONLY valid JSON" in prompt
    assert "Do NOT enclose your output in markdown code blocks" in prompt
    assert "Never Hallucinate" in prompt
    assert "null" in prompt


def test_build_analysis_prompt_empty_context():
    """Verify default prompt without context returns a generic instruction."""
    prompt = build_analysis_prompt(None)
    assert "Analyze the provided image and generate the conforming Knowledge Record JSON object." in prompt


def test_build_analysis_prompt_with_exif_context():
    """Verify context details are properly formatted and added to the user prompt."""
    context = {
        "taken_at": "2026-07-14T12:00:00Z",
        "camera_make": "Apple",
        "camera_model": "iPhone 15 Pro",
        "gps_latitude": 37.7749,
        "gps_longitude": -122.4194,
        "file_name": "vacation_photo.jpg"
    }
    prompt = build_analysis_prompt(context)
    assert "Capture Time: 2026-07-14T12:00:00Z" in prompt
    assert "Camera: Apple iPhone 15 Pro" in prompt
    assert "GPS Coordinates: Latitude 37.7749, Longitude -122.4194" in prompt
    assert "Original Filename: vacation_photo.jpg" in prompt
    assert "Use this context to resolve ambiguities" in prompt


# ─── 3. Response Parser Tests ───────────────────────────────────────────────

def test_parse_golden_knowledge_record():
    """Verify parsing a fully-populated, standard JSON record structure succeeds."""
    golden_json = """{
        "caption": "a family enjoying picnic in the park.",
        "detailed_description": "A mother, father, and two kids sitting on a red checkered blanket under a large oak tree. They are eating watermelon and smiling.",
        "scene": "park",
        "objects": ["Blanket", "watermelon", "Tree", "picnic basket"],
        "activities": ["picnicking", "eating", "Smiling"],
        "indoor_outdoor": "outdoor",
        "weather": "clear",
        "season": "summer",
        "dominant_colors": ["#4a90e2", "#ffffff", "#000000"],
        "people_count": 4,
        "detected_text": "Sunny Day Picnic",
        "document_type": null,
        "event_type": "picnic",
        "travel_event": false,
        "location_guess": "Golden Gate Park, San Francisco",
        "mood": "joyful",
        "keywords": ["picnic", "family", "fun", "park"],
        "ai_confidence": 0.95
    }"""
    result = parse_knowledge_record(golden_json)

    assert result.caption == "A family enjoying picnic in the park."
    assert result.detailed_description == "A mother, father, and two kids sitting on a red checkered blanket under a large oak tree. They are eating watermelon and smiling."
    assert result.scene == "park"
    assert result.objects == ["blanket", "picnic basket", "tree", "watermelon"]  # Sorted, lowercased
    assert result.activities == ["eating", "picnicking", "smiling"]              # Sorted, lowercased
    assert result.indoor_outdoor == "outdoor"
    assert result.weather == "clear"
    assert result.season == "summer"
    assert result.dominant_colors == ["#4A90E2", "#FFFFFF", "#000000"]
    assert result.people_count == 4
    assert result.detected_text == "Sunny Day Picnic"
    assert result.document_type is None
    assert result.event_type == "picnic"
    assert result.travel_event is False
    assert result.location_guess == "Golden Gate Park, San Francisco"
    assert result.mood == "joyful"
    assert result.keywords == {"tags": ["family", "fun", "park", "picnic"]}      # Sorted, lowercased, wrapped in dict
    assert result.ai_confidence == pytest.approx(0.95)
    assert isinstance(result.raw_response, dict)


def test_parse_minimal_knowledge_record():
    """Verify parsing a JSON record where all optional fields are set to null."""
    minimal_json = """{
        "caption": null,
        "detailed_description": null,
        "scene": null,
        "objects": null,
        "activities": null,
        "indoor_outdoor": null,
        "weather": null,
        "season": null,
        "dominant_colors": null,
        "people_count": null,
        "detected_text": null,
        "document_type": null,
        "event_type": null,
        "travel_event": null,
        "location_guess": null,
        "mood": null,
        "keywords": null,
        "ai_confidence": null
    }"""
    result = parse_knowledge_record(minimal_json)
    
    assert result.caption is None
    assert result.detailed_description is None
    assert result.scene is None
    assert result.objects is None
    assert result.activities is None
    assert result.indoor_outdoor is None
    assert result.weather is None
    assert result.season is None
    assert result.dominant_colors is None
    assert result.people_count is None
    assert result.detected_text is None
    assert result.document_type is None
    assert result.event_type is None
    assert result.travel_event is None
    assert result.location_guess is None
    assert result.mood is None
    assert result.keywords is None
    assert result.ai_confidence is None


def test_parse_json_wrapped_in_markdown_code_fences():
    """Verify parser strips code fences (```json ... ```) automatically before parsing."""
    raw_response = """```json
    {
        "caption": "a scenic view",
        "detailed_description": "ocean cliffs",
        "scene": "beach",
        "objects": [],
        "activities": [],
        "indoor_outdoor": "outdoor",
        "weather": "clear",
        "season": "summer",
        "dominant_colors": [],
        "people_count": 0,
        "detected_text": null,
        "document_type": null,
        "event_type": null,
        "travel_event": true,
        "location_guess": null,
        "mood": "serene",
        "keywords": [],
        "ai_confidence": 0.88
    }
    ```"""
    result = parse_knowledge_record(raw_response)
    assert result.caption == "A scenic view"
    assert result.scene == "beach"
    assert result.travel_event is True


def test_parse_invalid_json_raises_custom_error():
    """Verify that invalid JSON structures raise KnowledgeRecordParseError."""
    with pytest.raises(KnowledgeRecordParseError):
        parse_knowledge_record("Not JSON at all")

    with pytest.raises(KnowledgeRecordParseError):
        parse_knowledge_record("")

    with pytest.raises(KnowledgeRecordParseError):
        parse_knowledge_record("{ malformed JSON: 123 }")

    with pytest.raises(KnowledgeRecordParseError):
        parse_knowledge_record('["a", "list", "instead", "of", "dict"]')


# ─── 4. Normalization Rules Tests ───────────────────────────────────────────

def test_normalize_caption_first_letter_and_truncation():
    """Verify caption sentence-casing and truncation rules."""
    # Truncate
    long_caption = "a" * 600
    json_data = f'{{"caption": "{long_caption}"}}'
    result = parse_knowledge_record(json_data)
    assert len(result.caption) == 500
    assert result.caption.startswith("A")

    # Sentence casing
    result = parse_knowledge_record('{"caption": "  the dog jumped over a fence. "}')
    assert result.caption == "The dog jumped over a fence."


def test_normalize_detailed_description_truncation():
    """Verify detailed description truncation rules."""
    long_desc = "b" * 4500
    json_data = f'{{"detailed_description": "{long_desc}"}}'
    result = parse_knowledge_record(json_data)
    assert len(result.detailed_description) == 4000


def test_normalize_invalid_or_mismatched_enums_to_none():
    """Verify that invalid enum options are normalized to None."""
    json_data = """{
        "scene": "invalid_scene_name",
        "indoor_outdoor": "somewhere_else",
        "weather": "warm_breeze",
        "season": "monsoon",
        "document_type": "passport",
        "event_type": "sleepover",
        "mood": "bored"
    }"""
    result = parse_knowledge_record(json_data)
    assert result.scene is None
    assert result.indoor_outdoor is None
    assert result.weather is None
    assert result.season is None
    assert result.document_type is None
    assert result.event_type is None
    assert result.mood is None


def test_normalize_valid_enums_with_differing_casing():
    """Verify valid enum inputs are matched regardless of leading/trailing space or case."""
    json_data = """{
        "scene": "  CityScape ",
        "indoor_outdoor": "OuTdOoR",
        "weather": "CLEAR",
        "season": "Winter"
    }"""
    result = parse_knowledge_record(json_data)
    assert result.scene == "cityscape"
    assert result.indoor_outdoor == "outdoor"
    assert result.weather == "clear"
    assert result.season == "winter"


def test_normalize_objects_and_activities_arrays():
    """Verify arrays are lowercased, deduplicated, sorted, and limited in item count."""
    json_data = """{
        "objects": ["dog", "Dog", "cat", null, "tree", "Apple"],
        "activities": ["Running", "running", "jumping", "eating"]
    }"""
    result = parse_knowledge_record(json_data)
    assert result.objects == ["apple", "cat", "dog", "tree"]      # sorted & deduped
    assert result.activities == ["eating", "jumping", "running"]  # sorted & deduped


def test_normalize_objects_and_activities_truncation():
    """Verify that objects and activities lists are truncated at their respective max limits."""
    many_objects = [f"obj_{i}" for i in range(50)]
    many_activities = [f"act_{i}" for i in range(50)]
    
    json_data = json.dumps({
        "objects": many_objects,
        "activities": many_activities
    })
    result = parse_knowledge_record(json_data)
    
    assert len(result.objects) == 30
    assert len(result.activities) == 20


def test_normalize_dominant_colors():
    """Verify hex colors are validated, capitalized, '#' prefixed, and limited to 5."""
    json_data = """{
        "dominant_colors": ["#4a90e2", "ffffff", "invalid_color", "#ff0000", "000000", "#112233", "#445566"]
    }"""
    result = parse_knowledge_record(json_data)
    # 1. "#4a90e2" -> "#4A90E2"
    # 2. "ffffff" -> "#FFFFFF" (prefixed)
    # 3. "invalid_color" -> ignored
    # 4. "#ff0000" -> "#FF0000"
    # 5. "000000" -> "#000000"
    # 6. "#112233" -> "#112233"
    # 7. "#445566" -> ignored because max items is 5
    assert result.dominant_colors == ["#4A90E2", "#FFFFFF", "#FF0000", "#000000", "#112233"]


def test_normalize_people_count():
    """Verify clamping, float rounding, and invalid inputs for people count."""
    assert parse_knowledge_record('{"people_count": -5}').people_count == 0
    assert parse_knowledge_record('{"people_count": 150}').people_count == 100
    assert parse_knowledge_record('{"people_count": 3.4}').people_count == 3
    assert parse_knowledge_record('{"people_count": 5.7}').people_count == 6
    assert parse_knowledge_record('{"people_count": "12"}').people_count == 12
    assert parse_knowledge_record('{"people_count": "invalid"}').people_count is None


def test_normalize_ai_confidence():
    """Verify clamping and invalid input handling for confidence score."""
    assert parse_knowledge_record('{"ai_confidence": -0.2}').ai_confidence == 0.0
    assert parse_knowledge_record('{"ai_confidence": 1.5}').ai_confidence == 1.0
    assert parse_knowledge_record('{"ai_confidence": 0.85}').ai_confidence == pytest.approx(0.85)
    assert parse_knowledge_record('{"ai_confidence": "invalid"}').ai_confidence is None


def test_normalize_travel_event_bool():
    """Verify boolean normalization for travel event flags."""
    assert parse_knowledge_record('{"travel_event": "yes"}').travel_event is True
    assert parse_knowledge_record('{"travel_event": "1"}').travel_event is True
    assert parse_knowledge_record('{"travel_event": "FALSE"}').travel_event is False
    assert parse_knowledge_record('{"travel_event": "n"}').travel_event is False
    assert parse_knowledge_record('{"travel_event": "maybe"}').travel_event is None


def test_normalize_keywords_structure_and_limits():
    """Verify keywords (list of strings) normalize to lowercase, deduped, sorted, max 20, wrapped in dict."""
    json_data = """{
        "keywords": ["hiking", "mountain", "Hiking", "view", "cold", "snow", "backpacking"]
    }"""
    result = parse_knowledge_record(json_data)
    assert result.keywords == {
        "tags": ["backpacking", "cold", "hiking", "mountain", "snow", "view"]
    }

    # Verify limit of 20
    many_tags = [f"tag_{i}" for i in range(50)]
    result = parse_knowledge_record(json.dumps({"keywords": many_tags}))
    assert len(result.keywords["tags"]) == 20


# ─── 5. GeminiVisionProvider API Mock Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_provider_returns_none_when_no_api_key():
    """Verify GeminiVisionProvider returns None if GEMINI_API_KEY settings are missing."""
    from app.modules.media.services.ai_analysis.gemini_provider import GeminiVisionProvider
    from unittest.mock import patch

    provider = GeminiVisionProvider()
    with patch("app.modules.media.services.ai_analysis.gemini_provider.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = ""
        result = await provider.analyze("dummy_image.jpg")
        assert result is None


@pytest.mark.asyncio
async def test_gemini_provider_success():
    """Verify GeminiVisionProvider successfully parses a mock JSON response from Google GenAI."""
    from app.modules.media.services.ai_analysis.gemini_provider import GeminiVisionProvider
    from unittest.mock import MagicMock, patch

    provider = GeminiVisionProvider()
    with patch("app.modules.media.services.ai_analysis.gemini_provider.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test_api_key_123"
        with patch("PIL.Image.open") as mock_image_open:
            with patch("google.genai.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                
                mock_response = MagicMock()
                mock_response.text = '{"caption": "A cute cat", "detailed_description": "White cat on sofa", "scene": "home", "objects": ["cat"], "activities": [], "indoor_outdoor": "indoor", "weather": null, "season": null, "dominant_colors": ["#ffffff"], "people_count": 0, "detected_text": null, "document_type": null, "event_type": null, "travel_event": false, "location_guess": null, "mood": "peaceful", "keywords": ["cat"], "ai_confidence": 0.99}'
                mock_client.models.generate_content.return_value = mock_response

                result = await provider.analyze("dummy_image.jpg")

                assert result is not None
                assert result.caption == "A cute cat"
                assert result.scene == "home"
                assert result.people_count == 0
                assert result.keywords == {"tags": ["cat"]}
                assert result.ai_confidence == pytest.approx(0.99)
                mock_client_class.assert_called_once_with(api_key="test_api_key_123")


@pytest.mark.asyncio
async def test_gemini_provider_api_error():
    """Verify GeminiVisionProvider properly bubble up exception when Gemini API raises an error."""
    from app.modules.media.services.ai_analysis.gemini_provider import GeminiVisionProvider
    from unittest.mock import MagicMock, patch

    provider = GeminiVisionProvider()
    with patch("app.modules.media.services.ai_analysis.gemini_provider.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test_api_key_123"
        with patch("PIL.Image.open") as mock_image_open:
            with patch("google.genai.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content.side_effect = RuntimeError("API rate limit exceeded")

                with pytest.raises(RuntimeError) as exc_info:
                    await provider.analyze("dummy_image.jpg")

                assert "API rate limit exceeded" in str(exc_info.value)

