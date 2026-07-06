from datetime import datetime
from typing import Optional, List
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


class SearchResponse(BaseModel):
    items: List[SearchResultResponse]
    total: int
    limit: int
    offset: int

class MediaListResponse(BaseModel):
    items: List[MediaAssetResponse]
    total: int
    limit: int
    offset: int

