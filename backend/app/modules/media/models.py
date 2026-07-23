import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Enum, ForeignKey, Float, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class MediaType(str, enum.Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"

class AssetStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"

class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.UPLOADED, index=True, nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Soft Deletion / Recycle Bin
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    deleted_from: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    photo_metadata: Mapped[Optional["PhotoMetadata"]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan",
        uselist=False
    )
    embeddings: Mapped[List["MediaEmbedding"]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan"
    )
    ai_analysis: Mapped[Optional["ImageAIAnalysis"]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan",
        uselist=False
    )
    quality_assessment: Mapped[Optional["ImageQualityAssessment"]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan",
        uselist=False
    )

    @property
    def p_hash(self) -> Optional[str]:
        if self.ai_analysis and self.ai_analysis.keywords:
            return self.ai_analysis.keywords.get("p_hash")
        return None

class PhotoMetadata(Base):
    __tablename__ = "photo_metadata"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    camera_make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    camera_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exposure_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    f_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    iso_speed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Back-reference
    media_asset: Mapped["MediaAsset"] = relationship(back_populates="photo_metadata")

class MediaEmbedding(Base):
    __tablename__ = "media_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    vector_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    # Back-reference
    media_asset: Mapped["MediaAsset"] = relationship(back_populates="embeddings")

    # Constraints
    __table_args__ = (
        UniqueConstraint("media_asset_id", "model_name", name="uq_asset_model"),
    )

class AnalysisStatus(str, enum.Enum):
    """
    Lifecycle states for the AI Understanding Engine analysis pipeline.

    PENDING             — queued, not yet started
    PROCESSING          — provider call in-flight
    COMPLETED           — analysis succeeded, Knowledge Record persisted
    FAILED              — provider call or DB write failed; eligible for retry
    SKIPPED_NO_PROVIDER — no configured provider available (e.g. missing API key)
    """
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED_NO_PROVIDER = "SKIPPED_NO_PROVIDER"


class ImageAIAnalysis(Base):
    """
    Knowledge Record — structured semantic understanding of a media asset.

    One-to-one with MediaAsset. Designed for long-term extensibility: new fields
    from future provider outputs are added as nullable columns without schema breaks.

    Sections
    --------
    General           — processing lifecycle and provider identity
    Visual            — caption, scene, objects, activities
    Image Quality     — indoor/outdoor, weather, season, colors
    People            — head count
    Documents         — OCR text, document classification
    Memory            — event type, travel flag, location guess, mood, keywords
    AI Metadata       — confidence score, raw provider response, retry tracking
    """
    __tablename__ = "image_ai_analysis"

    # ── Primary Key ────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # ── General / Processing Lifecycle ─────────────────────────────────────────
    processing_status: Mapped[str] = mapped_column(
        String(30),
        default=AnalysisStatus.PENDING.value,
        nullable=False,
        index=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Legacy column — kept for backward compatibility with ingested records
    gemini_model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Visual Understanding ────────────────────────────────────────────────────
    caption: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    detailed_description: Mapped[Optional[str]] = mapped_column(String(4000), nullable=True)
    scene: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    objects: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    activities: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # ── Image Understanding ─────────────────────────────────────────────────────
    indoor_outdoor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Legacy boolean kept for backward compat; indoor_outdoor supersedes it
    is_indoor: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    weather: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    season: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dominant_colors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # ── People ──────────────────────────────────────────────────────────────────
    people_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Documents / OCR ────────────────────────────────────────────────────────
    detected_text: Mapped[Optional[str]] = mapped_column(String(8000), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Memory Understanding ────────────────────────────────────────────────────
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    travel_event: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    location_guess: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    estimated_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mood: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ── AI Metadata ─────────────────────────────────────────────────────────────
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    # ── Timestamps ──────────────────────────────────────────────────────────────
    analysis_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Back-reference
    media_asset: Mapped["MediaAsset"] = relationship(back_populates="ai_analysis")


class ImageQualityAssessment(Base):
    """
    Persistent Quality Record — structured multi-metric quality assessment of a media asset.

    One-to-one with MediaAsset. Persisted automatically during ingestion.

    Fields
    ------
    overall_score       Fused quality score [0.0, 1.0].
    quality_grade       QualityGrade enum name (EXCELLENT, GOOD, FAIR, POOR, VERY_POOR).
    sharpness_score     Measured sharpness score [0.0, 1.0] (or None if unmeasured).
    blur_score          Raw blur estimate from ingestion (or None).
    exposure_score      Measured exposure score [0.0, 1.0] (or None).
    brightness_score    Raw brightness mean [0.0, 1.0] (or None).
    aesthetic_score     Measured CLIP-IQA aesthetic score [0.0, 1.0] (or None).
    resolution_score    Measured resolution score [0.0, 1.0] (or None).
    confidence          Aggregate confidence score [0.0, 1.0].
    issues              JSON list of detected issue strings.
    recommendation      Human-readable recommendation summary.
    provider_versions   JSON dict mapping provider name -> provider semver.
    provider_scores     JSON dict with per-provider raw metric breakdowns.
    evaluated_at        Timestamp when evaluation was executed.
    """
    __tablename__ = "image_quality_assessments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    quality_grade: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    sharpness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    blur_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exposure_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brightness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    aesthetic_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    issues: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provider_versions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    provider_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Back-reference
    media_asset: Mapped["MediaAsset"] = relationship(back_populates="quality_assessment")
