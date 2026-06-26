import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Enum, ForeignKey, Float, UniqueConstraint
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
