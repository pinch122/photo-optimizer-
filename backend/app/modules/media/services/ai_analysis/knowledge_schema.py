"""
Knowledge Record Schema Definition.

Contains standard enums for controlled vocabulary fields and the master JSON Schema
defining the expected structure of vision model outputs.
"""

from __future__ import annotations

import enum
from typing import Any, Dict


class EventType(str, enum.Enum):
    BIRTHDAY = "birthday"
    WEDDING = "wedding"
    GRADUATION = "graduation"
    CONCERT = "concert"
    TRAVEL = "travel"
    HOLIDAY = "holiday"
    SPORTS = "sports"
    EXHIBITION = "exhibition"
    PARTY = "party"
    DINNER = "dinner"
    PICNIC = "picnic"
    HIKING = "hiking"
    CAMPING = "camping"
    CHRISTMAS = "christmas"
    NEW_YEAR = "new_year"
    THANKSGIVING = "thanksgiving"
    HALLOWEEN = "halloween"
    REUNION = "reunion"
    CONFERENCE = "conference"
    WORKSHOP = "workshop"
    PERFORMANCE = "performance"
    SPORTING_EVENT = "sporting_event"
    FAMILY_GATHERING = "family_gathering"
    CASUAL_OUTING = "casual_outing"
    CEREMONY = "ceremony"
    OTHER = "other"


class Mood(str, enum.Enum):
    JOYFUL = "joyful"
    PEACEFUL = "peaceful"
    ENERGETIC = "energetic"
    MELANCHOLIC = "melancholic"
    ROMANTIC = "romantic"
    MYSTERIOUS = "mysterious"
    DRAMATIC = "dramatic"
    NOSTALGIC = "nostalgic"
    TENSE = "tense"
    CELEBRATORY = "celebratory"
    SERENE = "serene"
    PLAYFUL = "playful"
    GLOOMY = "gloomy"
    UNKNOWN = "unknown"


class IndoorOutdoor(str, enum.Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    UNKNOWN = "unknown"


class Weather(str, enum.Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    SNOWY = "snowy"
    FOGGY = "foggy"
    STORMY = "stormy"
    OVERCAST = "overcast"
    WINDY = "windy"
    HAZY = "hazy"
    UNKNOWN = "unknown"


class Season(str, enum.Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    UNKNOWN = "unknown"


class DocumentType(str, enum.Enum):
    RECEIPT = "receipt"
    ID_CARD = "id_card"
    LETTER = "letter"
    SCREENSHOT = "screenshot"
    WHITEBOARD = "whiteboard"
    MENU = "menu"
    POSTER = "poster"
    BOOK_PAGE = "book_page"
    CERTIFICATE = "certificate"
    INVOICE = "invoice"
    TICKET = "ticket"
    HANDWRITTEN_NOTE = "handwritten_note"
    OTHER = "other"


class SceneType(str, enum.Enum):
    BEACH = "beach"
    MOUNTAIN = "mountain"
    CITYSCAPE = "cityscape"
    PARK = "park"
    RESTAURANT = "restaurant"
    OFFICE = "office"
    HOME = "home"
    SCHOOL = "school"
    GYM = "gym"
    FOREST = "forest"
    DESERT = "desert"
    GARDEN = "garden"
    STREET = "street"
    STORE = "store"
    MUSEUM = "museum"
    AIRPORT = "airport"
    CONCERT_HALL = "concert_hall"
    STADIUM = "stadium"
    HOTEL = "hotel"
    CLASSROOM = "classroom"
    UNKNOWN = "unknown"


KNOWLEDGE_RECORD_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ImageAIAnalysisRecord",
    "description": "Structured knowledge record output from vision analysis.",
    "type": "object",
    "properties": {
        "caption": {
            "type": ["string", "null"],
            "description": "A brief, one-sentence description of the image.",
            "maxLength": 500
        },
        "detailed_description": {
            "type": ["string", "null"],
            "description": "A detailed multi-sentence description detailing visual elements.",
            "maxLength": 4000
        },
        "scene": {
            "type": ["string", "null"],
            "enum": [s.value for s in SceneType] + [None],
            "description": "The category of environment shown in the image."
        },
        "objects": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "List of key objects present in the photo (e.g. car, cat, tree).",
            "maxItems": 30
        },
        "activities": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "List of activities depicted in the photo (e.g. running, laughing, cooking).",
            "maxItems": 20
        },
        "indoor_outdoor": {
            "type": ["string", "null"],
            "enum": [io.value for io in IndoorOutdoor] + [None],
            "description": "Indicates if the image was captured indoors or outdoors."
        },
        "weather": {
            "type": ["string", "null"],
            "enum": [w.value for w in Weather] + [None],
            "description": "Approximate weather conditions."
        },
        "season": {
            "type": ["string", "null"],
            "enum": [s.value for s in Season] + [None],
            "description": "Season of the year."
        },
        "dominant_colors": {
            "type": ["array", "null"],
            "items": {
                "type": "string",
                "pattern": "^#[0-9a-fA-F]{6}$"
            },
            "description": "Up to 5 dominant hex color codes.",
            "maxItems": 5
        },
        "people_count": {
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 100,
            "description": "Count of visible people in the photo."
        },
        "detected_text": {
            "type": ["string", "null"],
            "description": "OCR transcribed text detected within the image.",
            "maxLength": 4000
        },
        "document_type": {
            "type": ["string", "null"],
            "enum": [d.value for d in DocumentType] + [None],
            "description": "If the photo is a document, this classifies the document type."
        },
        "event_type": {
            "type": ["string", "null"],
            "enum": [e.value for e in EventType] + [None],
            "description": "Type of event if this photo captures a distinct event."
        },
        "travel_event": {
            "type": ["boolean", "null"],
            "description": "Flag representing whether this is likely a travel-related photo."
        },
        "location_guess": {
            "type": ["string", "null"],
            "description": "Synthesized guess of the location name or landmarks.",
            "maxLength": 200
        },
        "mood": {
            "type": ["string", "null"],
            "enum": [m.value for m in Mood] + [None],
            "description": "Estimated emotional atmosphere or mood of the image."
        },
        "keywords": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Extracted list of tags/keywords for hybrid search.",
            "maxItems": 20
        },
        "ai_confidence": {
            "type": ["number", "null"],
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence score of the vision model for this analysis."
        }
    },
    "required": [
        "caption",
        "detailed_description",
        "scene",
        "objects",
        "activities",
        "indoor_outdoor",
        "weather",
        "season",
        "dominant_colors",
        "people_count",
        "detected_text",
        "document_type",
        "event_type",
        "travel_event",
        "location_guess",
        "mood",
        "keywords",
        "ai_confidence"
    ],
    "additionalProperties": False
}


def get_schema_json() -> str:
    """Return JSON schema as a formatted string."""
    import json
    return json.dumps(KNOWLEDGE_RECORD_JSON_SCHEMA, indent=2)
