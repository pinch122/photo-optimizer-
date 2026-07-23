"""
Query Intent Service — Two-tier validation policy:
1. STRICT VALIDATION: Applied ONLY to document queries (receipt, passport, invoice, bill, etc.).
   Requires hard evidence (document_type, OCR text, or explicit document caption).
2. SEMANTIC VALIDATION: Applied to all object, scene, text, and general queries.
   Blends CLIP embedding similarity + scene + caption + keywords + objects.
"""

from typing import List, Dict, Any, Tuple, Optional
from enum import Enum
from app.modules.media.models import MediaAsset
from app.logging_config import logger


class QueryIntent(str, Enum):
    DOCUMENT = "DOCUMENT"
    OBJECT = "OBJECT"
    SCENE = "SCENE"
    TEXT = "TEXT"
    GENERAL = "GENERAL"


STRICT_DOCUMENT_KEYWORDS = {
    "receipt", "receipts", "passport", "passports", "invoice", "invoices",
    "bill", "bills", "license", "licence", "certificate", "id", "pan card",
    "aadhaar", "driving license", "identity card", "tax", "statement", "ticket", "document"
}

OBJECT_KEYWORDS = {
    "car", "cars", "dog", "dogs", "cat", "cats", "person", "people", "man", "woman",
    "flower", "flowers", "boat", "boats", "bird", "birds", "phone", "laptop",
    "bicycle", "airplane", "pizza", "food", "vehicle", "pet", "astronaut", "shoe",
    "bottle", "cup", "chair", "table"
}

SCENE_KEYWORDS = {
    "beach", "beaches", "mountain", "mountains", "forest", "forests", "desert",
    "snow", "sunset", "sunsets", "city", "street", "park", "indoor", "indoors",
    "outdoor", "outdoors", "ocean", "river", "landscape"
}

TEXT_KEYWORDS = {
    "phone number", "email", "address", "name", "document text", "text"
}


class IntentService:

    @staticmethod
    def classify_intent(query_text: str) -> Tuple[QueryIntent, str]:
        """
        Classify search query into QueryIntent and target entity term.
        """
        clean_query = query_text.lower().strip()
        words = set(clean_query.split())

        for kw in STRICT_DOCUMENT_KEYWORDS:
            if kw in clean_query or kw in words:
                return QueryIntent.DOCUMENT, kw

        for kw in OBJECT_KEYWORDS:
            if kw in clean_query or kw in words:
                return QueryIntent.OBJECT, kw

        for kw in SCENE_KEYWORDS:
            if kw in clean_query or kw in words:
                return QueryIntent.SCENE, kw

        for kw in TEXT_KEYWORDS:
            if kw in clean_query or kw in words:
                return QueryIntent.TEXT, kw

        return QueryIntent.GENERAL, clean_query

    @staticmethod
    def format_empty_message(query_text: str, intent: QueryIntent, target_entity: str) -> str:
        """
        Generate contextual empty message when no trustworthy candidates exist.
        """
        entity = target_entity.strip().lower()
        if intent == QueryIntent.DOCUMENT:
            if entity in {"receipt", "receipts"}:
                return "No receipts were found in your library."
            if entity in {"passport", "passports"}:
                return "No passport images were found in your library."
            if entity in {"invoice", "invoices"}:
                return "No invoices were found in your library."
            return f"No {entity} documents were found in your library."

        if intent == QueryIntent.OBJECT:
            return f"No {entity} photos were found in your library."

        if intent == QueryIntent.SCENE:
            return f"No {entity} photos were found in your library."

        return f"No matching photos found for '{query_text}'."

    @staticmethod
    def validate_asset_for_intent(
        asset: MediaAsset,
        intent: QueryIntent,
        target_entity: str,
        score: float
    ) -> Tuple[bool, str, List[str]]:
        """
        Validate candidate asset against query intent.

        1. STRICT VALIDATION (Hard Evidence Required)
           Applied ONLY to document queries (receipt, passport, invoice, bill, etc.).
           Requires explicit document evidence (document_type, OCR, or document caption).

        2. SEMANTIC VALIDATION (Flexible Multi-Signal)
           Applied to all object, scene, text, and general queries.
           Combines embedding similarity + scene + caption + keywords + objects.
           Rejects ONLY when explicit document contradiction occurs.
        """
        ai = asset.ai_analysis
        reasons: List[str] = []

        doc_type = (ai.document_type if ai and ai.document_type else "").lower()
        ocr_text = (ai.detected_text if ai and ai.detected_text else "").lower()
        caption = (ai.caption if ai and ai.caption else "").lower()
        scene = (ai.scene if ai and ai.scene else "").lower()
        objects = [o.lower() for o in (ai.objects if ai and ai.objects else [])]
        keywords = [k.lower() for k in (ai.keywords.keys() if ai and ai.keywords else [])]

        entity_stem = target_entity.rstrip("s")

        # ── 1. STRICT VALIDATION FOR DOCUMENT QUERIES ─────────────────────────
        if intent == QueryIntent.DOCUMENT:
            has_doc_type = bool(doc_type) and doc_type not in {"other", "unknown", "none"}
            doc_type_match = has_doc_type and (entity_stem in doc_type or doc_type in target_entity)
            ocr_match = bool(ocr_text) and (entity_stem in ocr_text or target_entity in ocr_text)
            caption_match = bool(caption) and (entity_stem in caption or target_entity in caption)

            if not (doc_type_match or ocr_match or caption_match):
                return False, "Low", []

            if doc_type_match:
                reasons.append(f"Document detected ({ai.document_type})")
            if ocr_match:
                reasons.append(f"OCR contains '{target_entity.capitalize()}'")
            if caption_match:
                reasons.append(f"Caption mentions '{target_entity}'")

            confidence = "Very High" if score >= 0.35 else "High"
            return True, confidence, reasons

        # ── 2. SEMANTIC VALIDATION FOR OBJECT / SCENE / GENERAL QUERIES ───────
        object_match = any(entity_stem in obj for obj in objects)
        scene_match = entity_stem in scene or target_entity in scene
        caption_match = entity_stem in caption or target_entity in caption
        keyword_match = any(entity_stem in kw for kw in keywords)

        if object_match:
            reasons.append(f"{target_entity.capitalize()} detected in image")
        if scene_match:
            reasons.append(f"{target_entity.capitalize()} scene classification")
        if caption_match:
            reasons.append(f"Caption mentions '{target_entity}'")
        if keyword_match:
            reasons.append(f"AI keyword match ({target_entity})")

        # Reject ONLY if explicit contradiction (e.g. document asset when searching for flowers/beach)
        if doc_type and doc_type in {"receipt", "passport", "invoice"} and intent in {QueryIntent.OBJECT, QueryIntent.SCENE}:
            return False, "Low", []

        # Reject OBJECT intent candidates with zero metadata evidence and low score (< 0.20)
        if intent == QueryIntent.OBJECT and len(reasons) == 0 and score < 0.20:
            return False, "Low", []

        # Assign confidence based on embedding score + metadata agreement
        if score >= 0.30 or len(reasons) >= 2:
            confidence = "Very High"
        elif score >= 0.20 or len(reasons) >= 1:
            confidence = "High"
        else:
            confidence = "Medium"

        return True, confidence, reasons
