"""
Configuration settings for the PhotoMind AI Ingestion Pipeline.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Setup Ingestion Logger
logger = logging.getLogger("ingest_pipeline")

def setup_ingestion_logging(log_dir: str = "logs", verbose: bool = False) -> None:
    """Configures structured logging to both console and logs/ingest.log."""
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "ingest.log")
    
    level = logging.DEBUG if verbose else logging.INFO
    log_format = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Root logger of pipeline
    logger.setLevel(level)
    logger.handlers.clear()
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    logger.info(f"Ingestion Logging initialized. Log file: {log_file_path}")


@dataclass
class IngestConfig:
    """Configuration options for the dataset ingestion script."""
    dataset_dir: Path = field(default_factory=lambda: Path("dataset/photomind_v1"))
    batch_size: int = 10
    max_workers: int = 4
    skip_embeddings: bool = False
    skip_gemini: bool = True  # Default to True unless configured/requested
    skip_quality: bool = False
    max_retries: int = 3
    supported_extensions: tuple = (".jpg", ".jpeg", ".png", ".webp")

    def discover_images(self) -> List[Path]:
        """Recursively scan dataset_dir to find all supported images."""
        if not self.dataset_dir.exists():
            logger.error(f"Dataset directory does not exist: {self.dataset_dir.resolve()}")
            return []
            
        images = []
        for root, _, files in os.walk(self.dataset_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.supported_extensions:
                    images.append(file_path)
                    
        return sorted(images)
