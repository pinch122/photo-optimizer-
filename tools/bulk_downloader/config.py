"""
Configuration constants for the PhotoMind AI Bulk Image Downloader.

All settings can be overridden via CLI arguments or environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DownloaderConfig:
    """Immutable configuration for the bulk download pipeline."""

    # ─── API Settings ───────────────────────────────────────────────
    base_url: str = "https://picsum.photos"
    list_endpoint: str = "/v2/list"
    page_size: int = 100  # Max items per page (Picsum API limit)

    # ─── Image Settings ─────────────────────────────────────────────
    image_width: int = 1024
    image_height: int = 768
    image_format: str = "jpg"

    # ─── Download Settings ───────────────────────────────────────────
    max_images: int = 10_000
    max_workers: int = 30
    max_retries: int = 3
    retry_delay_base: float = 1.0  # Exponential backoff base (seconds)
    request_timeout: int = 30  # HTTP timeout per request (seconds)

    # ─── Storage Settings ────────────────────────────────────────────
    output_dir: Path = field(default_factory=lambda: Path("downloaded_images"))
    failed_log: str = "failed_downloads.txt"

    @property
    def list_url(self) -> str:
        """Full URL for the image listing API endpoint."""
        return f"{self.base_url}{self.list_endpoint}"

    def download_url(self, image_id: str) -> str:
        """Generate the direct download URL for a specific image ID."""
        return f"{self.base_url}/id/{image_id}/{self.image_width}/{self.image_height}.{self.image_format}"

    def image_path(self, image_id: str) -> Path:
        """Return the local filesystem path for a given image ID."""
        return self.output_dir / f"{image_id}.{self.image_format}"

    def ensure_dirs(self) -> None:
        """Create output directories if they do not exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
