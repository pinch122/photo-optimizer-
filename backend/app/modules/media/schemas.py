from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.modules.media.models import MediaType, AssetStatus

class PhotoMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    width: int
    height: int
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    exposure_time: Optional[str] = None
    f_number: Optional[str] = None
    iso_speed: Optional[int] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None

class AIAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Processing lifecycle
    processing_status: Optional[str] = None
    processed_at: Optional[datetime] = None
    model_name: Optional[str] = None

    # Visual understanding
    caption: Optional[str] = None
    detailed_description: Optional[str] = None
    scene: Optional[str] = None
    objects: Optional[List[str]] = None
    activities: Optional[List[str]] = None

    # Image understanding
    indoor_outdoor: Optional[str] = None
    is_indoor: Optional[bool] = None          # legacy — kept for frontend compat
    weather: Optional[str] = None
    season: Optional[str] = None
    dominant_colors: Optional[List[str]] = None

    # People
    people_count: Optional[int] = None

    # Documents / OCR
    detected_text: Optional[str] = None
    document_type: Optional[str] = None

    # Memory understanding
    event_type: Optional[str] = None
    travel_event: Optional[bool] = None
    location_guess: Optional[str] = None
    estimated_location: Optional[str] = None  # legacy alias
    mood: Optional[str] = None
    keywords: Optional[Dict[str, Any]] = None

    # AI metadata
    ai_confidence: Optional[float] = None

class MediaAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    mime_type: str
    media_type: MediaType
    file_size: int
    status: AssetStatus
    taken_at: datetime
    created_at: datetime
    photo_metadata: Optional[PhotoMetadataResponse] = None
    p_hash: Optional[str] = None
    ai_analysis: Optional[AIAnalysisResponse] = None

class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    media_type: MediaType
    file_size: int
    status: AssetStatus
    created_at: datetime

class StatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: AssetStatus
    error_message: Optional[str] = None

class SearchResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    mime_type: str
    media_type: MediaType
    file_size: int
    status: AssetStatus
    taken_at: datetime
    created_at: datetime
    score: float
    explanation: Optional[List[str]] = None
    photo_metadata: Optional[PhotoMetadataResponse] = None
    p_hash: Optional[str] = None
    ai_analysis: Optional[AIAnalysisResponse] = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[SearchResultResponse]
    total: int
    limit: int
    offset: int


class SimilarImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    thumbnail_url: str
    original_url: str
    similarity_score: float
    similarity_percentage: float

class MediaListResponse(BaseModel):
    items: List[MediaAssetResponse]
    total: int
    limit: int
    offset: int
