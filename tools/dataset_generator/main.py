"""
PhotoMind AI — Synthetic Dataset Generator

CLI entry point for generating categorized image datasets from source images.
Produces approximately 1,000 images across 8 categories (originals + 7 transforms)
for testing AI pipelines: CLIP embeddings, semantic search, duplicate detection,
image quality analysis, and more.

Usage:
    python -m tools.dataset_generator.main
    python -m tools.dataset_generator.main --source dataset/originals --output dataset/photomind_v1
    python -m tools.dataset_generator.main --duplicates 200 --blurred 100
"""

import argparse
import logging
import sys

from pathlib import Path

from .config import GeneratorConfig
from .generator import DatasetGenerator


def setup_logging(verbose: bool = False) -> None:
    """Configure structured console logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="photomind-dataset-generator",
        description=(
            "Generate synthetic image datasets from source images "
            "for testing PhotoMind AI pipelines."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m tools.dataset_generator.main\n"
            "  python -m tools.dataset_generator.main --source ./my_images --output ./test_dataset\n"
            "  python -m tools.dataset_generator.main --duplicates 200 --blurred 100 --dark 100\n"
        ),
    )

    # ─── Path Arguments ─────────────────────────────────────────────
    parser.add_argument(
        "--source", type=str, default="dataset/originals",
        help="Source directory containing original images (default: dataset/originals)",
    )
    parser.add_argument(
        "--output", type=str, default="dataset/photomind_v1",
        help="Output directory for the generated dataset (default: dataset/photomind_v1)",
    )

    # ─── Category Counts ────────────────────────────────────────────
    parser.add_argument(
        "--duplicates", type=int, default=100,
        help="Number of exact duplicates to generate (default: 100)",
    )
    parser.add_argument(
        "--resized", type=int, default=100,
        help="Number of resized/compressed images (default: 100)",
    )
    parser.add_argument(
        "--blurred", type=int, default=75,
        help="Number of blurred images (default: 75)",
    )
    parser.add_argument(
        "--dark", type=int, default=75,
        help="Number of dark/underexposed images (default: 75)",
    )
    parser.add_argument(
        "--bright", type=int, default=50,
        help="Number of overexposed images (default: 50)",
    )
    parser.add_argument(
        "--rotated", type=int, default=50,
        help="Number of rotated images (default: 50)",
    )
    parser.add_argument(
        "--cropped", type=int, default=50,
        help="Number of cropped images (default: 50)",
    )

    # ─── Options ────────────────────────────────────────────────────
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducible dataset generation",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug-level logging output",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the dataset generator CLI."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logger = logging.getLogger("dataset_generator.main")

    # Set random seed if specified
    if args.seed is not None:
        import random
        random.seed(args.seed)
        logger.info("Random seed set to %d for reproducible generation.", args.seed)

    # Build configuration from CLI args
    config = GeneratorConfig(
        source_dir=Path(args.source),
        output_dir=Path(args.output),
        num_duplicates=args.duplicates,
        num_resized=args.resized,
        num_blurred=args.blurred,
        num_dark=args.dark,
        num_bright=args.bright,
        num_rotated=args.rotated,
        num_cropped=args.cropped,
    )

    # Print configuration banner
    logger.info("=" * 64)
    logger.info("  PhotoMind AI — Synthetic Dataset Generator")
    logger.info("=" * 64)
    logger.info("  Source Dir     : %s", config.source_dir.resolve())
    logger.info("  Output Dir     : %s", config.output_dir.resolve())
    logger.info("-" * 64)
    for category, count in config.category_counts.items():
        logger.info("    %-14s : %d images", category, count)
    logger.info("-" * 64)
    logger.info("  Total Transforms : %d", config.total_transforms)
    logger.info("  Target Total     : ~%d images (originals + transforms)", config.total_transforms + 500)
    logger.info("=" * 64)

    # Execute the generation pipeline
    try:
        generator = DatasetGenerator(config)
        stats = generator.generate()
        print(stats.summary())
        logger.info("Dataset generation complete.")
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error(
            "Please ensure your source images are in: %s",
            config.source_dir.resolve(),
        )
        sys.exit(1)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Generation interrupted by user. Partial dataset preserved.")
        sys.exit(130)


if __name__ == "__main__":
    main()
