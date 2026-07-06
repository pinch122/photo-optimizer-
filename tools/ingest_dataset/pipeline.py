"""
Core dataset ingestion pipeline for PhotoMind AI.
Processes image datasets in batches, computes metadata, hashes, quality scores,
generates embeddings, and stores everything in PostgreSQL and Qdrant.
"""

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from PIL import Image
from sqlalchemy import select
from tqdm import tqdm

# Import backend application modules
from app.config import settings
from app.database import async_session
from app.modules.media.models import (
    MediaAsset,
    PhotoMetadata,
    MediaEmbedding,
    ImageAIAnalysis,
    MediaType,
    AssetStatus,
)
from app.modules.media.services.hashing_service import HashingService
from app.modules.media.services.storage_service import StorageService
from app.modules.media.services.thumb_service import ThumbnailService
from app.modules.media.services.metadata_service import MetadataService
from app.modules.media.services.embedding_service import EmbeddingService
from app.modules.media.services.qdrant_service import QdrantService

from .config import IngestConfig, logger
from .quality import analyze_image_quality

# Perceptual hash helper (dHash)
def compute_phash(file_path: Path) -> str:
    """Computes a 64-bit difference perceptual hash (dHash) of the image."""
    try:
        with Image.open(file_path) as img:
            img = img.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
            pixels = list(img.getdata())
            
            diff = []
            for row in range(8):
                for col in range(8):
                    pixel_left = pixels[row * 9 + col]
                    pixel_right = pixels[row * 9 + col + 1]
                    diff.append(pixel_left > pixel_right)
            
            decimal_val = 0
            for index, value in enumerate(diff):
                if value:
                    decimal_val += 2 ** index
            return f"{decimal_val:016x}"
    except Exception as e:
        logger.error(f"Perceptual hash computation failed for {file_path}: {e}")
        return "0" * 16

@dataclass
class IngestStats:
    """Statistics accumulator for ingestion pipeline sessions."""
    found: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0

    def summary(self) -> str:
        """Format a human-readable summary block."""
        mins, secs = divmod(self.elapsed_seconds, 60)
        return (
            f"\n{'=' * 60}\n"
            f"  DATASET INGESTION SUMMARY\n"
            f"{'=' * 60}\n"
            f"  Images Found    : {self.found:,}\n"
            f"  Imported        : {self.imported:,}\n"
            f"  Skipped (exist) : {self.skipped:,}\n"
            f"  Failed          : {self.failed:,}\n"
            f"  Elapsed Time    : {int(mins)}m {secs:.1f}s\n"
            f"{'=' * 60}"
        )


class DatasetIngestionPipeline:
    """Batch-oriented ingestion pipeline for PhotoMind AI."""

    def __init__(self, config: IngestConfig) -> None:
        self.config = config
        self.stats = IngestStats()

    async def process_single_image(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single image:
        Compute hashes, run quality analysis, generate thumbnails, compute CLIP embeddings.
        """
        # 1. Compute SHA256
        with open(file_path, "rb") as f:
            sha256_hash = HashingService.calculate_sha256(f)

        # Check existing in PostgreSQL (restart-safe check)
        async with async_session() as session:
            query = select(MediaAsset).where(MediaAsset.file_hash == sha256_hash)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            if existing:
                return {"status": "skipped", "hash": sha256_hash}

        # New asset ID
        asset_id = uuid.uuid4()
        original_path = ""
        thumbnail_path = ""
        
        try:
            # 2. Save original copy to persistent storage
            with open(file_path, "rb") as f:
                original_path = await StorageService.save_original(f, asset_id)

            # 3. Extract metadata
            metadata = await MetadataService.extract_metadata(original_path)

            # 4. Generate & Save WebP Thumbnail
            thumbnail_bytes = await ThumbnailService.generate_thumbnail(
                original_path, size=settings.THUMBNAIL_SIZE
            )
            thumbnail_path = await StorageService.save_thumbnail(thumbnail_bytes, asset_id)

            # 5. Compute Perceptual Hash (dHash)
            p_hash = compute_phash(Path(original_path))

            # 6. Quality Analysis
            quality_data = {}
            if not self.config.skip_quality:
                quality_data = analyze_image_quality(original_path)

            # 7. CLIP Vector Embedding with exponential backoff retries
            vector = None
            if not self.config.skip_embeddings:
                for attempt in range(self.config.max_retries):
                    try:
                        vector = await EmbeddingService.generate_embedding(original_path)
                        break
                    except Exception as embed_err:
                        if attempt == self.config.max_retries - 1:
                            raise embed_err
                        wait_time = 1.0 * (attempt + 1)
                        logger.warning(
                            f"Embedding generation attempt {attempt + 1} failed for {file_path.name}: {embed_err}. Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)

            # 8. Gemini description (Stub/Placeholder unless configured)
            caption = None
            if not self.config.skip_gemini:
                caption = f"A photo of filename {file_path.name} with aspect ratio {metadata['width']}x{metadata['height']}"

            # Return success details
            return {
                "status": "success",
                "id": asset_id,
                "filename": file_path.name,
                "mime_type": f"image/{file_path.suffix[1:].lower().replace('jpg', 'jpeg')}",
                "file_size": file_path.stat().st_size,
                "file_hash": sha256_hash,
                "original_path": original_path,
                "thumbnail_path": thumbnail_path,
                "metadata": metadata,
                "p_hash": p_hash,
                "quality_data": quality_data,
                "vector": vector,
                "caption": caption,
            }

        except Exception as e:
            logger.error(f"Failed processing image {file_path.name}: {e}", exc_info=True)
            # Cleanup any files written
            if original_path:
                StorageService.delete_file(original_path)
            if thumbnail_path:
                StorageService.delete_file(thumbnail_path)
            return {"status": "failed", "error": str(e), "file_path": str(file_path)}

    async def save_to_databases(self, data: Dict[str, Any]) -> bool:
        """Persists media models to PostgreSQL and indices vectors to Qdrant."""
        asset_id = data["id"]
        vector = data["vector"]
        metadata = data["metadata"]
        quality_data = data["quality_data"]

        async with async_session() as session:
            try:
                # 1. Index vector in Qdrant (if generated)
                if vector:
                    taken_timestamp = (
                        int(metadata["taken_at"].timestamp())
                        if metadata["taken_at"]
                        else int(datetime.now(timezone.utc).timestamp())
                    )
                    payload = {
                        "id": str(asset_id),
                        "filename": data["filename"],
                        "taken_at": taken_timestamp,
                    }
                    QdrantService.upsert_vector(
                        asset_id=asset_id,
                        vector=vector,
                        model_name=settings.CLIP_MODEL_NAME,
                        payload=payload,
                    )

                # 2. PostgreSQL: MediaAsset
                media_asset = MediaAsset(
                    id=asset_id,
                    filename=data["filename"],
                    mime_type=data["mime_type"],
                    media_type=MediaType.PHOTO,
                    file_size=data["file_size"],
                    file_hash=data["file_hash"],
                    status=AssetStatus.READY,
                    original_path=data["original_path"],
                    thumbnail_path=data["thumbnail_path"],
                    taken_at=metadata["taken_at"] if metadata["taken_at"] else datetime.now(timezone.utc)
                )
                session.add(media_asset)

                # 3. PostgreSQL: PhotoMetadata
                photo_meta = PhotoMetadata(
                    id=uuid.uuid4(),
                    media_asset_id=asset_id,
                    width=metadata["width"],
                    height=metadata["height"],
                    camera_make=metadata["camera_make"],
                    camera_model=metadata["camera_model"],
                    exposure_time=metadata["exposure_time"],
                    f_number=metadata["f_number"],
                    iso_speed=metadata["iso_speed"],
                    gps_latitude=metadata["gps_latitude"],
                    gps_longitude=metadata["gps_longitude"]
                )
                session.add(photo_meta)

                # 4. PostgreSQL: MediaEmbedding (if generated)
                if vector:
                    media_embedding = MediaEmbedding(
                        id=uuid.uuid4(),
                        media_asset_id=asset_id,
                        model_name=settings.CLIP_MODEL_NAME,
                        vector_dimension=len(vector)
                    )
                    session.add(media_embedding)

                # 5. PostgreSQL: ImageAIAnalysis to store caption and quality data
                ai_analysis = ImageAIAnalysis(
                    id=uuid.uuid4(),
                    media_asset_id=asset_id,
                    caption=data["caption"],
                    # Store quality scores and pHash inside JSON keywords column to keep existing schema
                    keywords={
                        "p_hash": data["p_hash"],
                        "blur_score": quality_data.get("blur_score"),
                        "brightness": quality_data.get("brightness"),
                        "darkness": quality_data.get("darkness"),
                        "sharpness": quality_data.get("sharpness"),
                        "is_screenshot": quality_data.get("is_screenshot")
                    },
                    gemini_model_version="gemini-2.5-flash" if data["caption"] else None
                )
                session.add(ai_analysis)

                await session.commit()
                return True

            except Exception as save_err:
                logger.error(f"Database commit error for asset [{asset_id}]: {save_err}")
                await session.rollback()
                # Clean Qdrant
                try:
                    if vector:
                        QdrantService.delete_vector(asset_id, settings.CLIP_MODEL_NAME)
                except Exception:
                    pass
                # Clean Files
                StorageService.delete_file(data["original_path"])
                StorageService.delete_file(data["thumbnail_path"])
                return False

    async def ingest(self) -> IngestStats:
        """Run the full ingestion pipeline across discovered files."""
        start_time = time.perf_counter()
        
        # Discover images
        image_paths = self.config.discover_images()
        self.stats = IngestStats(found=len(image_paths))
        
        if not image_paths:
            logger.info("No images found for ingestion.")
            return self.stats

        logger.info(f"Starting ingestion pipeline: found {self.stats.found} target images.")
        
        # Split into batches
        batches = [
            image_paths[i:i + self.config.batch_size]
            for i in range(0, len(image_paths), self.config.batch_size)
        ]
        
        # Progress bar
        with tqdm(
            total=len(image_paths),
            desc="Processing images",
            unit="img",
            ncols=100
        ) as pbar:
            for batch in batches:
                # Process the batch concurrently
                tasks = [self.process_single_image(path) for path in batch]
                results = await asyncio.gather(*tasks)
                
                # Process result of each image
                for file_path, res in zip(batch, results):
                    status = res["status"]
                    
                    if status == "skipped":
                        self.stats.skipped += 1
                    elif status == "failed":
                        self.stats.failed += 1
                        logger.error(f"Image ingestion failed for {file_path.name}: {res.get('error')}")
                    elif status == "success":
                        # Save successful processing to PostgreSQL/Qdrant
                        saved = await self.save_to_databases(res)
                        if saved:
                            self.stats.imported += 1
                        else:
                            self.stats.failed += 1
                    
                    pbar.update(1)
                    pbar.set_postfix(
                        imported=self.stats.imported,
                        skip=self.stats.skipped,
                        fail=self.stats.failed,
                    )
        
        self.stats.elapsed_seconds = time.perf_counter() - start_time
        
        # Write manifest.json
        self._write_manifest()
        
        return self.stats

    def _write_manifest(self) -> None:
        """Write manifest.json mapping the ingestion outcomes."""
        manifest_path = self.config.dataset_dir / "manifest.json"
        
        manifest_data = {
            "total_images": self.stats.found,
            "imported": self.stats.imported,
            "duplicates_skipped": self.stats.skipped,
            "failed": self.stats.failed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "processing_time_seconds": round(self.stats.elapsed_seconds, 2)
        }
        
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)
            logger.info(f"Wrote ingestion manifest to {manifest_path}")
        except Exception as err:
            logger.error(f"Failed to write manifest.json: {err}")
