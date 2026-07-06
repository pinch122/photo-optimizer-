"""
Synthetic dataset generation engine for PhotoMind AI.

Orchestrates the pipeline: discover source images → copy originals →
apply randomized transforms → save to categorized subdirectories.
Restart-safe (never overwrites existing files), with progress tracking.
"""

import shutil
import random
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from PIL import Image
from tqdm import tqdm

from .config import GeneratorConfig
from .transforms import (
    TRANSFORM_REGISTRY,
    _extract_exif,
    _save_with_exif,
)

logger = logging.getLogger("dataset_generator.generator")


@dataclass
class GenerationStats:
    """Accumulator for dataset generation statistics."""

    originals_copied: int = 0
    originals_skipped: int = 0
    transforms_generated: int = 0
    transforms_skipped: int = 0
    transforms_failed: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    @property
    def total_output(self) -> int:
        """Total images in the output dataset."""
        return self.originals_copied + self.originals_skipped + self.transforms_generated + self.transforms_skipped

    def summary(self) -> str:
        """Return a formatted summary string."""
        mins, secs = divmod(self.elapsed_seconds, 60)
        lines = [
            "",
            "=" * 64,
            "  DATASET GENERATION STATISTICS",
            "=" * 64,
            f"  Originals Copied     : {self.originals_copied:,}",
            f"  Originals Skipped    : {self.originals_skipped:,}",
            f"  Transforms Generated : {self.transforms_generated:,}",
            f"  Transforms Skipped   : {self.transforms_skipped:,}",
            f"  Transforms Failed    : {self.transforms_failed:,}",
            "-" * 64,
        ]
        for category, count in sorted(self.category_counts.items()):
            lines.append(f"    {category:<20s} : {count:>5,}")
        lines.extend([
            "-" * 64,
            f"  Total Output Images  : ~{self.total_output:,}",
            f"  Elapsed Time         : {int(mins)}m {secs:.1f}s",
            "=" * 64,
        ])
        return "\n".join(lines)


class DatasetGenerator:
    """
    Orchestrates synthetic dataset creation from a set of source images.

    Pipeline:
        1. Discover source images in the source directory.
        2. Copy originals to the output originals/ subdirectory.
        3. For each transform category, randomly select sources and apply transforms.
        4. Save transformed images to their respective subdirectories.
        5. Write a manifest.json summarizing all generated files.
    """

    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config
        self.stats = GenerationStats()
        self._source_images: List[Path] = []

    def _discover_sources(self) -> List[Path]:
        """
        Scan the source directory for supported image files.

        Returns:
            Sorted list of absolute paths to source images.

        Raises:
            FileNotFoundError: If the source directory does not exist.
            ValueError: If no images are found.
        """
        source_dir = self.config.source_dir

        if not source_dir.exists():
            raise FileNotFoundError(
                f"Source directory does not exist: {source_dir.resolve()}"
            )

        images = sorted([
            f for f in source_dir.iterdir()
            if f.is_file() and f.suffix.lower() in self.config.supported_extensions
        ])

        if not images:
            raise ValueError(
                f"No supported images found in {source_dir.resolve()}. "
                f"Supported formats: {', '.join(self.config.supported_extensions)}"
            )

        logger.info("Discovered %d source images in %s", len(images), source_dir)
        return images

    def _copy_originals(self) -> None:
        """Copy all source images to the output originals/ subdirectory."""
        originals_dir = self.config.subdirectories["originals"]

        logger.info("Phase 1: Copying %d originals...", len(self._source_images))

        for src_path in tqdm(
            self._source_images,
            desc="Copying originals",
            unit="img",
            ncols=100,
        ):
            dest_path = originals_dir / src_path.name

            if dest_path.exists():
                self.stats.originals_skipped += 1
                continue

            shutil.copy2(src_path, dest_path)  # copy2 preserves metadata
            self.stats.originals_copied += 1

    def _generate_category(self, category: str, count: int) -> None:
        """
        Generate transformed images for a single category.

        Args:
            category: The transform category name (must be in TRANSFORM_REGISTRY).
            count: Number of images to generate for this category.
        """
        transform_fn = TRANSFORM_REGISTRY[category]
        output_dir = self.config.subdirectories[category]
        generated = 0
        skipped = 0
        failed = 0

        # Randomly sample source images with replacement
        selected_sources = random.choices(self._source_images, k=count)

        for idx, src_path in enumerate(
            tqdm(
                selected_sources,
                desc=f"Generating {category}",
                unit="img",
                ncols=100,
            )
        ):
            # Build output filename: <category>_<index>_<source_stem>.jpg
            output_name = f"{category}_{idx:04d}_{src_path.stem}.jpg"
            output_path = output_dir / output_name

            # Restart-safe: skip if already exists
            if output_path.exists():
                skipped += 1
                continue

            try:
                img = Image.open(src_path).convert("RGB")
                exif_bytes = _extract_exif(Image.open(src_path))

                # Apply the transform
                transformed, metadata = transform_fn(img, self.config.transforms)

                # Determine JPEG quality
                if category == "resized":
                    quality = metadata.get("quality", 40)
                elif category == "duplicates":
                    quality = 95  # near-lossless for exact duplicates
                else:
                    quality = 92

                # Save with EXIF preservation
                _save_with_exif(transformed, str(output_path), exif_bytes, quality)
                generated += 1

                img.close()

            except Exception as e:
                logger.warning(
                    "Failed to generate %s from %s: %s",
                    output_name, src_path.name, e,
                )
                failed += 1
                # Clean up partial file
                if output_path.exists():
                    output_path.unlink(missing_ok=True)

        self.stats.transforms_generated += generated
        self.stats.transforms_skipped += skipped
        self.stats.transforms_failed += failed
        self.stats.category_counts[category] = generated + skipped

        logger.info(
            "  %s: %d generated, %d skipped, %d failed",
            category, generated, skipped, failed,
        )

    def _write_manifest(self) -> None:
        """Write a manifest.json summarizing the generated dataset."""
        manifest = {
            "generator": "PhotoMind AI Synthetic Dataset Generator",
            "source_dir": str(self.config.source_dir.resolve()),
            "output_dir": str(self.config.output_dir.resolve()),
            "source_image_count": len(self._source_images),
            "categories": {},
        }

        for category, subdir in self.config.subdirectories.items():
            files = sorted([
                f.name for f in subdir.iterdir()
                if f.is_file() and f.suffix.lower() in self.config.supported_extensions
            ])
            manifest["categories"][category] = {
                "count": len(files),
                "directory": str(subdir.resolve()),
            }

        manifest_path = self.config.output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info("Wrote dataset manifest to %s", manifest_path)

    def generate(self) -> GenerationStats:
        """
        Execute the full dataset generation pipeline.

        Returns:
            GenerationStats with counts and timing.
        """
        start_time = time.perf_counter()

        # Step 0: Setup
        self._source_images = self._discover_sources()
        self.config.ensure_dirs()
        self.stats = GenerationStats()

        # Step 1: Copy originals
        self._copy_originals()

        # Step 2: Generate transforms for each category
        logger.info(
            "Phase 2: Generating %d transforms across %d categories...",
            self.config.total_transforms,
            len(self.config.category_counts),
        )

        for category, count in self.config.category_counts.items():
            self._generate_category(category, count)

        # Step 3: Write manifest
        self._write_manifest()

        self.stats.elapsed_seconds = time.perf_counter() - start_time
        return self.stats
