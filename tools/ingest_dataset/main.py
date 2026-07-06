"""
PhotoMind AI — Dataset Ingestion Pipeline CLI

Discovers, processes, and imports generated synthetic image datasets
reusing core backend services (PostgreSQL, Qdrant, CLIP embeddings, image processing).

Usage:
    python -m tools.ingest_dataset.main
    python -m tools.ingest_dataset.main --dataset dataset/photomind_v1 --batch-size 20
"""

import os
import sys

# ─── Environment Variable Overrides ─────────────────────────────────────────
# These MUST be set before any backend module imports.
# Configures host-level loopback connectivity to services inside Docker.
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["QDRANT_HOST"] = "localhost"
# Redirect storage and cache folders to workspace directories
os.environ["STORAGE_PATH"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage")
)
os.environ["HUGGINGFACE_CACHE_DIR"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage", "hf_cache")
)

# Append backend directory to path so we can resolve app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

import argparse
import asyncio
import logging
from pathlib import Path

from .config import IngestConfig, setup_ingestion_logging, logger
from .pipeline import DatasetIngestionPipeline


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="photomind-ingestion-pipeline",
        description="Ingest synthetic photo datasets into the PhotoMind AI database & search index.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m tools.ingest_dataset.main\n"
            "  python -m tools.ingest_dataset.main --batch-size 20 --workers 8\n"
            "  python -m tools.ingest_dataset.main --skip-embeddings --skip-quality\n"
        ),
    )
    parser.add_argument(
        "--dataset", type=str, default="dataset/photomind_v1",
        help="Path to the dataset directory (default: dataset/photomind_v1)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Number of images to process concurrently in a batch (default: 10)",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Concurrence worker capacity for embedding steps (default: 4)",
    )
    parser.add_argument(
        "--skip-embeddings", action="store_true",
        help="Skip CLIP vector embedding generation and Qdrant indexing",
    )
    parser.add_argument(
        "--skip-gemini", action="store_true",
        help="Skip Gemini LLM descriptions generation (default)",
    )
    parser.add_argument(
        "--skip-quality", action="store_true",
        help="Skip image quality scoring metrics extraction",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug-level console output logging",
    )
    return parser.parse_args()


async def async_main() -> None:
    """Async main routine."""
    args = parse_args()
    
    # 1. Setup logging
    setup_ingestion_logging(verbose=args.verbose)
    
    # 2. Build configuration
    config = IngestConfig(
        dataset_dir=Path(args.dataset),
        batch_size=args.batch_size,
        max_workers=args.workers,
        skip_embeddings=args.skip_embeddings,
        skip_gemini=args.skip_gemini,
        skip_quality=args.skip_quality,
    )
    
    # Log configuration banner
    logger.info("=" * 64)
    logger.info("  PhotoMind AI — Ingestion Pipeline CLI")
    logger.info("=" * 64)
    logger.info("  Dataset Dir     : %s", config.dataset_dir.resolve())
    logger.info("  Batch Size      : %d", config.batch_size)
    logger.info("  Workers         : %d", config.max_workers)
    logger.info("  Skip Embeddings : %s", config.skip_embeddings)
    logger.info("  Skip Gemini     : %s", config.skip_gemini)
    logger.info("  Skip Quality    : %s", config.skip_quality)
    logger.info("  Storage Path    : %s", os.environ["STORAGE_PATH"])
    logger.info("=" * 64)
    
    # Verify connections before starting
    try:
        from app.database import check_db_connection
        from app.qdrant_client_helper import check_qdrant_connection
        
        db_ok = await check_db_connection()
        if not db_ok:
            logger.error("Could not connect to PostgreSQL database. Verify Docker container status.")
            sys.exit(1)
            
        if not config.skip_embeddings:
            qdrant_ok = await check_qdrant_connection()
            if not qdrant_ok:
                logger.error("Could not connect to Qdrant vector database. Verify Docker container status.")
                sys.exit(1)
                
    except Exception as connection_err:
        logger.error(f"Failed verifying service dependencies connectivity: {connection_err}")
        sys.exit(1)
        
    # Execute pipeline
    pipeline = DatasetIngestionPipeline(config)
    stats = await pipeline.ingest()
    
    # Print summary
    print(stats.summary())


def main() -> None:
    """Synchronous entry point wrapping async main loop."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.warning("Ingestion session interrupted by user. Partial progress saved.")
        sys.exit(130)


if __name__ == "__main__":
    main()
