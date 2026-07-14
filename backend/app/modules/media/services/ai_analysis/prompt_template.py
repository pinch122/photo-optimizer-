"""
Production prompt templates and builder for the AI Understanding Engine.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from app.modules.media.services.ai_analysis.knowledge_schema import get_schema_json


SYSTEM_PROMPT = f"""You are an expert photo analyst for a personal photo management system (PhotoMind AI).
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

### CRITICAL SAFETY AND GROUNDING RULES
Describe ONLY what is visually observable. Never invent facts. Never guess or hallucinate.
- Never infer a person's identity or name.
- Never infer family relationships (e.g. mother, father, husband, wife, son, daughter, friend, etc.).
- Never infer occupations.
- Never infer nationality, religion, ethnicity, or political affiliation.
- Never infer health conditions or disabilities.
- Never infer age beyond these broad categories: child, teenager, adult, older adult.
- Never infer emotions as facts. Instead, describe observable facial expressions or body language (e.g. Bad: "The family is happy." Good: "Four people are smiling while sitting together.").
- Never infer locations unless supported by visible landmarks or readable text in the image.
- Never infer events beyond visually supported evidence. Use broad event categories instead.
- If uncertain about any field, return null. Never guess.

### TARGET JSON SCHEMA:
{get_schema_json()}
"""


def get_system_prompt() -> str:
    """Return the static system prompt instructing the model on schema and formatting."""
    return SYSTEM_PROMPT


def build_analysis_prompt(image_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Build the user prompt, incorporating optional image context (EXIF, metadata) to improve accuracy.

    Parameters
    ----------
    image_context : dict, optional
        Contains hints from EXIF or other sources, such as:
        - "taken_at": iso-formatted timestamp
        - "camera_make": make of the camera
        - "camera_model": model of the camera
        - "gps_latitude": float
        - "gps_longitude": float
        - "file_name": name of the image file

    Returns
    -------
    str
        The complete prompt instructing the model to analyze the image under the given context constraints.
    """
    base_prompt = "Analyze the provided image and generate the conforming Knowledge Record JSON object."

    if not image_context:
        return base_prompt

    context_lines = []
    if "taken_at" in image_context and image_context["taken_at"]:
        context_lines.append(f"- Capture Time: {image_context['taken_at']}")
    if "camera_make" in image_context and image_context["camera_make"]:
        context_lines.append(f"- Camera: {image_context['camera_make']} {image_context.get('camera_model', '')}".strip())
    if "gps_latitude" in image_context and "gps_longitude" in image_context:
        lat = image_context["gps_latitude"]
        lng = image_context["gps_longitude"]
        if lat is not None and lng is not None:
            context_lines.append(f"- GPS Coordinates: Latitude {lat}, Longitude {lng}")
    if "file_name" in image_context and image_context["file_name"]:
        context_lines.append(f"- Original Filename: {image_context['file_name']}")

    if context_lines:
        context_str = "\n".join(context_lines)
        return (
            f"{base_prompt}\n\n"
            f"Here is some reliable, pre-extracted context from the file's metadata to assist your analysis:\n"
            f"{context_str}\n\n"
            f"Use this context to resolve ambiguities (for example, using GPS coordinates to determine the location or timestamps for the season/event, if applicable)."
        )

    return base_prompt
