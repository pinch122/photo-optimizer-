"""
PhotoMind AI — Bulk Image Downloader

Entry point for downloading large image datasets from Lorem Picsum
for testing AI pipelines (CLIP embeddings, semantic search, OCR, duplicate detection).

Usage:
    python -m tools.bulk_downloader.main --count 10000 --workers 30
    python -m tools.bulk_downloader.main --count 500 --width 1920 --height 1080
    python -m tools.bulk_downloader.main --output ./test_images --count 100
"""

import argparse
import logging
import sys
from pathlib import Path

from .config import DownloaderConfig
from .client import PicsumClient
from .downloader import BulkDownloader


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
        prog="photomind-bulk-downloader",
        description="Download large image datasets from Lorem Picsum for PhotoMind AI testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m tools.bulk_downloader.main --count 10000\n"
            "  python -m tools.bulk_downloader.main --count 500 --width 1920 --height 1080\n"
            "  python -m tools.bulk_downloader.main --output ./my_images --workers 50\n"
        ),
    )
    parser.add_argument(
        "--count", type=int, default=10_000,
        help="Number of images to download (default: 10000, max: 100000)",
    )
    parser.add_argument(
        "--width", type=int, default=1024,
        help="Image width in pixels (default: 1024)",
    )
    parser.add_argument(
        "--height", type=int, default=768,
        help="Image height in pixels (default: 768)",
    )
    parser.add_argument(
        "--workers", type=int, default=30,
        help="Number of concurrent download threads (default: 30, range: 1-50)",
    )
    parser.add_argument(
        "--output", type=str, default="downloaded_images",
        help="Output directory for downloaded images (default: downloaded_images)",
    )
    parser.add_argument(
        "--retries", type=int, default=3,
        help="Maximum retry attempts per failed download (default: 3)",
    )
    parser.add_argument(
        "--timeout", type=int, default=30,
        help="HTTP request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug-level logging output",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the bulk downloader CLI."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logger = logging.getLogger("bulk_downloader.main")

    # Validate arguments
    if args.count < 1 or args.count > 100_000:
        logger.error("--count must be between 1 and 100,000. Got: %d", args.count)
        sys.exit(1)
    if args.workers < 1 or args.workers > 50:
        logger.error("--workers must be between 1 and 50. Got: %d", args.workers)
        sys.exit(1)

    # Build configuration
    config = DownloaderConfig(
        max_images=args.count,
        image_width=args.width,
        image_height=args.height,
        max_workers=args.workers,
        output_dir=Path(args.output),
        max_retries=args.retries,
        request_timeout=args.timeout,
    )

    logger.info("=" * 60)
    logger.info("  PhotoMind AI — Bulk Image Downloader")
    logger.info("=" * 60)
    logger.info("  Target Count : %s images", f"{config.max_images:,}")
    logger.info("  Resolution   : %dx%d", config.image_width, config.image_height)
    logger.info("  Workers      : %d threads", config.max_workers)
    logger.info("  Output Dir   : %s", config.output_dir.resolve())
    logger.info("  Retries      : %d per image", config.max_retries)
    logger.info("  Timeout      : %ds per request", config.request_timeout)
    logger.info("=" * 60)

    # Phase 1: Fetch image metadata
    logger.info("Phase 1: Fetching image metadata from Picsum API...")
    client = PicsumClient(config)
    try:
        image_ids = client.fetch_image_ids()
    finally:
        client.close()

    if not image_ids:
        logger.error("No image IDs found. Check your network connection.")
        sys.exit(1)

    logger.info("Collected %d unique image IDs.", len(image_ids))

    # Phase 2: Download images
    logger.info("Phase 2: Starting concurrent downloads...")
    downloader = BulkDownloader(config)
    stats = downloader.download(image_ids)

    # Phase 3: Print statistics
    print(stats.summary())

    if stats.failed > 0:
        failed_log_path = config.output_dir / config.failed_log
        logger.warning(
            "%d images failed. See %s for IDs to retry.",
            stats.failed,
            failed_log_path,
        )

    logger.info("Bulk download session complete.")


if __name__ == "__main__":
    main()
