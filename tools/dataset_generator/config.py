"""
Configuration for the PhotoMind AI Synthetic Dataset Generator.

Defines source/output paths, dataset counts per category,
and transform parameters. All settings can be overridden via CLI.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class TransformParams:
    """Parameters controlling the intensity/range of each transform type."""

    # ─── Resize / Compress ──────────────────────────────────────────
    resize_scale_min: float = 0.25
    resize_scale_max: float = 0.75
    jpeg_quality_min: int = 15
    jpeg_quality_max: int = 50

    # ─── Blur ───────────────────────────────────────────────────────
    blur_radius_min: float = 2.0
    blur_radius_max: float = 8.0

    # ─── Brightness ─────────────────────────────────────────────────
    darken_factor_min: float = 0.15
    darken_factor_max: float = 0.45
    brighten_factor_min: float = 1.6
    brighten_factor_max: float = 2.5

    # ─── Rotation ───────────────────────────────────────────────────
    rotation_angles: tuple = (90, 180, 270)
    arbitrary_rotation_min: float = 5.0
    arbitrary_rotation_max: float = 45.0
    arbitrary_rotation_chance: float = 0.3  # 30% chance of arbitrary angle

    # ─── Crop ───────────────────────────────────────────────────────
    crop_ratio_min: float = 0.4
    crop_ratio_max: float = 0.75


@dataclass
class GeneratorConfig:
    """Top-level configuration for the dataset generation pipeline."""

    # ─── Paths ──────────────────────────────────────────────────────
    source_dir: Path = field(default_factory=lambda: Path("dataset/originals"))
    output_dir: Path = field(default_factory=lambda: Path("dataset/photomind_v1"))

    # ─── Dataset Counts ─────────────────────────────────────────────
    num_duplicates: int = 100
    num_resized: int = 100
    num_blurred: int = 75
    num_dark: int = 75
    num_bright: int = 50
    num_rotated: int = 50
    num_cropped: int = 50

    # ─── Transform Parameters ───────────────────────────────────────
    transforms: TransformParams = field(default_factory=TransformParams)

    # ─── Image Format ───────────────────────────────────────────────
    supported_extensions: tuple = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")

    @property
    def total_transforms(self) -> int:
        """Total number of transformed images to generate."""
        return (
            self.num_duplicates
            + self.num_resized
            + self.num_blurred
            + self.num_dark
            + self.num_bright
            + self.num_rotated
            + self.num_cropped
        )

    @property
    def category_counts(self) -> Dict[str, int]:
        """Map of category name → target count."""
        return {
            "duplicates": self.num_duplicates,
            "resized": self.num_resized,
            "blurred": self.num_blurred,
            "dark": self.num_dark,
            "bright": self.num_bright,
            "rotated": self.num_rotated,
            "cropped": self.num_cropped,
        }

    @property
    def subdirectories(self) -> Dict[str, Path]:
        """Map of category name → output subdirectory path."""
        return {
            "originals": self.output_dir / "originals",
            "duplicates": self.output_dir / "duplicates",
            "resized": self.output_dir / "resized",
            "blurred": self.output_dir / "blurred",
            "dark": self.output_dir / "dark",
            "bright": self.output_dir / "bright",
            "rotated": self.output_dir / "rotated",
            "cropped": self.output_dir / "cropped",
        }

    def ensure_dirs(self) -> None:
        """Create all output subdirectories if they do not exist."""
        for subdir in self.subdirectories.values():
            subdir.mkdir(parents=True, exist_ok=True)
