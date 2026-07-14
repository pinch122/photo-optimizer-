"""
Response Parser and Normalization Layer for the AI Understanding Engine.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from app.modules.media.services.ai_analysis.base_provider import AnalysisResult
from app.modules.media.services.ai_analysis.knowledge_schema import (
    DocumentType,
    EventType,
    IndoorOutdoor,
    Mood,
    SceneType,
    Season,
    Weather,
)

E = TypeVar("E", bound=type)


class KnowledgeRecordParseError(Exception):
    """Raised when the vision provider's response cannot be parsed or is fundamentally malformed."""
    pass


def parse_knowledge_record(raw_text: str) -> AnalysisResult:
    """
    Parse a raw string response from a vision provider into a normalized AnalysisResult.

    Parameters
    ----------
    raw_text : str
        The raw response text from the vision provider.

    Returns
    -------
    AnalysisResult
        The normalized and validated analysis result.

    Raises
    -------
    KnowledgeRecordParseError
        If the response is not valid JSON or cannot be parsed.
    """
    if not raw_text or not raw_text.strip():
        raise KnowledgeRecordParseError("Empty response received from provider.")

    cleaned_text = raw_text.strip()

    # Strip markdown code fences if the model disobeyed prompt instructions
    if cleaned_text.startswith("```"):
        # Remove opening fence (e.g. ```json or just ```)
        cleaned_text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned_text)
        # Remove closing fence
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
        cleaned_text = cleaned_text.strip()

    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        raise KnowledgeRecordParseError(f"Failed to parse JSON response: {e}") from e

    if not isinstance(data, dict):
        raise KnowledgeRecordParseError("Provider response parsed to non-object JSON structure.")

    # Apply Normalization Rules
    normalized = AnalysisResult(
        caption=_normalize_string(data.get("caption"), max_len=500, sentence_case=True),
        detailed_description=_normalize_string(data.get("detailed_description"), max_len=4000),
        scene=_normalize_enum(data.get("scene"), SceneType),
        objects=_normalize_string_list(data.get("objects"), max_items=30),
        activities=_normalize_string_list(data.get("activities"), max_items=20),
        indoor_outdoor=_normalize_enum(data.get("indoor_outdoor"), IndoorOutdoor),
        weather=_normalize_enum(data.get("weather"), Weather),
        season=_normalize_enum(data.get("season"), Season),
        dominant_colors=_normalize_colors(data.get("dominant_colors")),
        people_count=_normalize_people_count(data.get("people_count")),
        detected_text=_normalize_string(data.get("detected_text"), max_len=4000),
        document_type=_normalize_enum(data.get("document_type"), DocumentType),
        event_type=_normalize_enum(data.get("event_type"), EventType),
        travel_event=_normalize_bool(data.get("travel_event")),
        location_guess=_normalize_string(data.get("location_guess"), max_len=200),
        mood=_normalize_enum(data.get("mood"), Mood),
        keywords=_normalize_keywords(data.get("keywords")),
        ai_confidence=_normalize_confidence(data.get("ai_confidence")),
        raw_response=data
    )

    return normalized


# ─── Private Normalization Helpers ───────────────────────────────────────────

def _normalize_string(val: Any, max_len: int, sentence_case: bool = False) -> Optional[str]:
    """Normalize string values: strip, enforce max length, capitalize if requested."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "n/a", "none"):
        return None
    
    # Truncate to max length
    s = s[:max_len]

    if sentence_case and s:
        # Sentence-case the first letter of the string
        s = s[0].upper() + s[1:]
    return s


def _normalize_enum(val: Any, enum_cls: Any) -> Optional[str]:
    """Validate and normalize enum values against controlled vocabularies."""
    if val is None:
        return None
    s = str(val).strip().lower()
    for item in enum_cls:
        if item.value == s:
            return item.value
    return None


def _normalize_string_list(val: Any, max_items: int) -> Optional[List[str]]:
    """Clean, lowercase, deduplicate, sort, and truncate string arrays."""
    if val is None:
        return None
    if not isinstance(val, list):
        return None

    cleaned = []
    for item in val:
        if item is not None:
            s = str(item).strip().lower()
            if s and s not in ("null", "n/a", "none"):
                cleaned.append(s)

    # Deduplicate preserving order (or sorted order)
    deduped = sorted(list(set(cleaned)))
    return deduped[:max_items]


def _normalize_colors(val: Any) -> Optional[List[str]]:
    """Validate and normalize dominant hex colors to standard uppercase #RRGGBB."""
    if val is None:
        return None
    if not isinstance(val, list):
        return None

    cleaned = []
    hex_pattern = re.compile(r"^#?[0-9a-fA-F]{6}$")

    for item in val:
        if item is not None:
            s = str(item).strip()
            if hex_pattern.match(s):
                # Ensure it starts with '#' and is uppercase for consistency
                if not s.startswith("#"):
                    s = "#" + s
                cleaned.append(s.upper())

    # Limit to max 5 items
    return cleaned[:5]


def _normalize_people_count(val: Any) -> Optional[int]:
    """Convert and clamp people count to 0-100 range."""
    if val is None:
        return None
    try:
        # Convert float to int, handles string numbers
        n = int(round(float(val)))
        # Clamp to [0, 100]
        return max(0, min(100, n))
    except (ValueError, TypeError):
        return None


def _normalize_confidence(val: Any) -> Optional[float]:
    """Convert and clamp confidence score to 0.0-1.0 range."""
    if val is None:
        return None
    try:
        f = float(val)
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, f))
    except (ValueError, TypeError):
        return None


def _normalize_bool(val: Any) -> Optional[bool]:
    """Normalize boolean fields."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def _normalize_keywords(val: Any) -> Optional[dict]:
    """
    Normalize semantic tags/keywords array and wrap in a database-compatible dictionary.
    Input raw response: list of strings (array).
    Output: dict with key "tags" containing list of strings, or None.
    """
    if val is None:
        return None
    
    # If the provider somehow sent a dict, try to extract the list of tags
    if isinstance(val, dict):
        tags = val.get("tags")
        if tags is not None:
            val = tags
        else:
            # Fallback: if it's already a dict but lacks 'tags', just return it as is or empty
            return val

    normalized_list = _normalize_string_list(val, max_items=20)
    if normalized_list is None:
        return None
        
    return {"tags": normalized_list}
