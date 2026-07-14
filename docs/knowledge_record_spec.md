# Knowledge Record Specification & Prompt Engineering Guide

This document defines the PhotoMind AI **Knowledge Record** (persisted in PostgreSQL as `ImageAIAnalysis`) and the vision model prompt design for Sprint 5.5.

---

## 1. Overview & Architecture

PhotoMind AI is transitioning from a standard photo gallery into an **AI Memory Operating System**. Understanding the context of every image requires a vision AI provider. To prevent vendor lock-in and simplify testing, the system decouples provider implementations from the core query layer.

A key part of this decoupling is translating raw provider outputs into a normalized, type-safe schema: the **Knowledge Record**. 

```
   Raw Model Output
          ↓
[ response_parser.py ] (Stripping markdown, loading JSON, applying normalization/clamping)
          ↓
   AnalysisResult (dataclass)
          ↓
[ analysis_service.py ]
          ↓
ImageAIAnalysis (PostgreSQL Record)
```

---

## 2. Field Rationale & Feature Mapping

Every field in the schema is carefully chosen to support a specific core experience of the Memory OS:

| Field | JSON Type | DB Type | Description / Constraints | Target Features Supported |
|---|---|---|---|---|
| `caption` | `string` \| `null` | `VARCHAR(1000)` | Brief, one-sentence caption describing the photo. Max 500 chars. | **Hybrid Search**, **Chat (RAG)**, auto-generating album titles. |
| `detailed_description` | `string` \| `null` | `VARCHAR(4000)` | Multi-sentence detailed description of the photo. Max 4000 chars. | **Chat (RAG)** context, accessibility readers, deep narrative search. |
| `scene` | `string` \| `null` | `VARCHAR(255)` | Category of environment (e.g. `beach`, `mountain`). Defined by `SceneType` enum. | **Smart Albums** (e.g. auto-grouping beach photos). |
| `objects` | `array` \| `null` | `JSON` | List of key objects detected (e.g., `dog`, `car`). Max 30 items. | **Semantic Search** filtering, Object-level query indexing. |
| `activities` | `array` \| `null` | `JSON` | List of activities depicted (e.g., `running`, `eating`). Max 20 items. | **Timeline view**, Activity search, sports/hobby categorization. |
| `indoor_outdoor` | `string` \| `null` | `VARCHAR(20)` | `indoor` \| `outdoor` \| `unknown`. Keeps legacy `is_indoor` in sync. | Environmental filtering (e.g. "show outdoor photos"). |
| `weather` | `string` \| `null` | `VARCHAR(100)` | Weather condition (e.g. `clear`, `rainy`). Defined by `Weather` enum. | Weather Timeline, contextual UI backgrounds, Smart Albums. |
| `season` | `string` \| `null` | `VARCHAR(100)` | Season of the year (e.g. `summer`). Defined by `Season` enum. | Seasonal highlights (e.g. "Summer Memories" throwback). |
| `dominant_colors` | `array` \| `null` | `JSON` | Up to 5 hex codes (e.g. `["#4A90E2", "#FFFFFF"]`). | Color-based aesthetics search, dynamic UI accent matching. |
| `people_count` | `integer` \| `null` | `INTEGER` | Number of visible people in the photo. Clamped between 0 and 100. | **Social Graph** grouping, "Group Photos" auto-album, filtering portraits. |
| `detected_text` | `string` \| `null` | `VARCHAR(8000)` | OCR text transcribed from the image. Max 4000 chars. | **Document Detection**, search inside screenshots/receipts/whiteboards. |
| `document_type` | `string` \| `null` | `VARCHAR(100)` | Categorizes document (e.g. `receipt`, `screenshot`). Defined by `DocumentType` enum. | **Document Detection** automatic archiving and filing. |
| `event_type` | `string` \| `null` | `VARCHAR(100)` | Categorizes event (e.g. `birthday`, `wedding`). Defined by `EventType` enum. | **Event Timeline**, Smart Albums for life milestones. |
| `travel_event` | `boolean` \| `null` | `BOOLEAN` | Flags if photo belongs to a trip or vacation. | Travel albums, mapping itineraries, Trip timeline view. |
| `location_guess` | `string` \| `null` | `VARCHAR(255)` | Synthesized landmark/city guess (e.g., "Eiffel Tower"). Max 200 chars. | **Map View** clustering, geographical timeline matching. |
| `mood` | `string` \| `null` | `VARCHAR(100)` | Atmosphere/mood (e.g. `peaceful`, `joyful`). Defined by `Mood` enum. | Mood boards, mood-based slideshow tracks. |
| `keywords` | `array` \| `null` | `JSON` | List of tags for hybrid search. Wrapped in DB as `{"tags": [...]}`. Max 20. | **Hybrid Search** fallback tags, tag clouds. |
| `ai_confidence` | `number` \| `null` | `FLOAT` | Reliability score of output between 0.0 and 1.0. | Quality audit, triggering re-analysis on low scores. |

---

## 3. Controlled Vocabularies (Enums)

To ensure consistency across queries and filters, the following fields use strict lowercase enums:

### EventType
`birthday`, `wedding`, `graduation`, `concert`, `travel`, `holiday`, `sports`, `exhibition`, `party`, `dinner`, `picnic`, `hiking`, `camping`, `christmas`, `new_year`, `thanksgiving`, `halloween`, `reunion`, `conference`, `workshop`, `performance`, `sporting_event`, `family_gathering`, `casual_outing`, `ceremony`, `other`

### Mood
`joyful`, `peaceful`, `energetic`, `melancholic`, `romantic`, `mysterious`, `dramatic`, `nostalgic`, `tense`, `celebratory`, `serene`, `playful`, `gloomy`, `unknown`

### SceneType
`beach`, `mountain`, `cityscape`, `park`, `restaurant`, `office`, `home`, `school`, `gym`, `forest`, `desert`, `garden`, `street`, `store`, `museum`, `airport`, `concert_hall`, `stadium`, `hotel`, `classroom`, `unknown`

### IndoorOutdoor
`indoor`, `outdoor`, `unknown`

### Weather
`clear`, `cloudy`, `rainy`, `snowy`, `foggy`, `stormy`, `overcast`, `windy`, `hazy`, `unknown`

### Season
`spring`, `summer`, `autumn`, `winter`, `unknown`

### DocumentType
`receipt`, `id_card`, `letter`, `screenshot`, `whiteboard`, `menu`, `poster`, `book_page`, `certificate`, `invoice`, `ticket`, `handwritten_note`, `other`

---

## 4. Production Vision Model Prompt

This is the system prompt that will be sent to vision models (like Gemini 1.5 Flash in Sprint 6). It is designed to maximize JSON formatting compliance and prevent hallucination.

```
You are an expert photo analyst for a personal photo management system (PhotoMind AI).
Your task is to analyze the user's photo and generate a highly structured Knowledge Record summarizing its contents, environment, context, and metadata.

You must strictly output ONLY valid JSON that conforms to the JSON schema provided below.
Do NOT enclose your output in markdown code blocks (e.g. do not wrap with ```json or ```).
Do NOT include any explanatory text, preambles, introductions, or trailing explanations.
Your entire response must be a single, parseable JSON object.

### RULES FOR VALUE EXTRACTION
1. **Never Hallucinate:** If you cannot determine the value of a field with high confidence, you MUST set it to `null`. Do not make guesses or invent information.
2. **Controlled Vocabularies:** For fields with enums, you must choose one of the provided values (all lowercase) or set it to `null`. Do not use any values outside the defined list.
3. **Array Constraints:** Do not exceed the maximum number of items specified for list fields (e.g., maximum 30 for objects, 20 for activities, 20 for keywords, 5 for dominant_colors).
4. **Dominant Colors:** Provide up to 5 dominant color hex codes (e.g. "#4a90e2"). Ensure they are valid 6-character hexadecimal codes starting with '#'.
5. **No Placeholders:** Never use filler text or placeholders like "N/A", "unknown", or "none" for string fields. Use `null` instead.

### TARGET JSON SCHEMA:
{
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
      "enum": ["beach", "mountain", "cityscape", "park", "restaurant", "office", "home", "school", "gym", "forest", "desert", "garden", "street", "store", "museum", "airport", "concert_hall", "stadium", "hotel", "classroom", "unknown", null],
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
      "enum": ["indoor", "outdoor", "unknown", null],
      "description": "Indicates if the image was captured indoors or outdoors."
    },
    "weather": {
      "type": ["string", "null"],
      "enum": ["clear", "cloudy", "rainy", "snowy", "foggy", "stormy", "overcast", "windy", "hazy", "unknown", null],
      "description": "Approximate weather conditions."
    },
    "season": {
      "type": ["string", "null"],
      "enum": ["spring", "summer", "autumn", "winter", "unknown", null],
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
      "enum": ["receipt", "id_card", "letter", "screenshot", "whiteboard", "menu", "poster", "book_page", "certificate", "invoice", "ticket", "handwritten_note", "other", null],
      "description": "If the photo is a document, this classifies the document type."
    },
    "event_type": {
      "type": ["string", "null"],
      "enum": ["birthday", "wedding", "graduation", "concert", "travel", "holiday", "sports", "exhibition", "party", "dinner", "picnic", "hiking", "camping", "christmas", "new_year", "thanksgiving", "halloween", "reunion", "conference", "workshop", "performance", "sporting_event", "family_gathering", "casual_outing", "ceremony", "other", null],
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
      "enum": ["joyful", "peaceful", "energetic", "melancholic", "romantic", "mysterious", "dramatic", "nostalgic", "tense", "celebratory", "serene", "playful", "gloomy", "unknown", null],
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
  "additionalProperties": false
}
```

---

## 5. Metadata Integration (EXIF & Context)

To improve quality and bypass vision provider visual estimation issues, reliable pre-extracted EXIF metadata is injected directly into the user prompt:

* **Capture Time:** Helps determine `season` and `event_type` (e.g. Christmas, New Year).
* **Camera Model:** Used to resolve visual resolution and source characteristics.
* **GPS Coordinates:** Essential for resolving landmarks/locations (`location_guess`), local time offsets, and travel status (`travel_event`).
* **Original Filename:** Helps identify document types or specific context clues.

---

## 6. Example Conforming Output (Golden JSON)

```json
{
  "caption": "A family enjoying picnic in the park.",
  "detailed_description": "A mother, father, and two kids sitting on a red checkered blanket under a large oak tree. They are eating watermelon and smiling.",
  "scene": "park",
  "objects": ["blanket", "picnic basket", "tree", "watermelon"],
  "activities": ["eating", "picnicking", "smiling"],
  "indoor_outdoor": "outdoor",
  "weather": "clear",
  "season": "summer",
  "dominant_colors": ["#4A90E2", "#FFFFFF", "#000000"],
  "people_count": 4,
  "detected_text": "Sunny Day Picnic",
  "document_type": null,
  "event_type": "picnic",
  "travel_event": false,
  "location_guess": "Golden Gate Park, San Francisco",
  "mood": "joyful",
  "keywords": ["family", "fun", "park", "picnic"],
  "ai_confidence": 0.95
}
```

---

## 7. Normalization and Resiliency Logic

The parsing engine (`response_parser.py`) guarantees structural validity even when models fail to follow instructions perfectly:

1. **Markdown Stripping:** Strips any trailing or leading markdown syntax (e.g., ` ```json ` fences).
2. **First-Letter Capitalization:** Automatically capitalizes the first letter of `caption` for standard display.
3. **Enum Fallback:** Any value that does not match the strict enum choices is fallback-normalized to `null`.
4. **List Cleaning:** Deduplicates, lowercases, sorts, and truncates list arrays (objects, activities, keywords) to their maximum lengths to maintain index sizing.
5. **Color Standards:** Regex matches, uppercase-normalizes, and prepends `#` to color hex strings. Discards non-hex colors.
6. **Range Clamping:** Clamps `people_count` to `[0, 100]` and `ai_confidence` to `[0.0, 1.0]`. Rounds float-based counts to closest integer.
7. **Database Compatibility:** Wraps standard array keyword tags into a nested `"tags"` dictionary: `{"tags": [...]}` to maintain compatibility with legacy JSON database mappings.
