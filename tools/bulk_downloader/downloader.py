"""
Concurrent bulk image downloader engine.

Uses ThreadPoolExecutor for parallel downloads with retry logic,
skip-already-downloaded resilience, and structured failure logging.
"""

import time
import logging
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

from .config import DownloaderConfig

logger = logging.getLogger("bulk_downloader.downloader")


@dataclass
class DownloadStats:
    """Accumulator for download session statistics."""

    total_requested: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    failed_ids: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate the percentage of successful downloads."""
        attempted = self.downloaded + self.failed
        if attempted == 0:
            return 0.0
        return (self.downloaded / attempted) * 100

    def summary(self) -> str:
        """Return a formatted summary string."""
        mins, secs = divmod(self.elapsed_seconds, 60)
        return (
            f"\n{'=' * 60}\n"
            f"  DOWNLOAD STATISTICS\n"
            f"{'=' * 60}\n"
            f"  Total Requested : {self.total_requested:,}\n"
            f"  Downloaded      : {self.downloaded:,}\n"
            f"  Skipped (exist) : {self.skipped:,}\n"
            f"  Failed          : {self.failed:,}\n"
            f"  Success Rate    : {self.success_rate:.1f}%\n"
            f"  Elapsed Time    : {int(mins)}m {secs:.1f}s\n"
            f"{'=' * 60}"
        )


class BulkDownloader:
    """
    Thread-pool based image downloader with automatic retry,
    resume support, and progress tracking.
    """

    def __init__(self, config: DownloaderConfig) -> None:
        self.config = config
        self.stats = DownloadStats()

    def _build_session(self) -> requests.Session:
        """Create a download-optimized requests session."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_delay_base,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.max_workers,
            pool_maxsize=self.config.max_workers,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _download_single(
        self, session: requests.Session, image_id: str
    ) -> Dict[str, Any]:
        """
        Download a single image by ID.

        Returns:
            A dict with keys: id, status ('downloaded', 'skipped', 'failed'), error (optional).
        """
        dest_path = self.config.image_path(image_id)

        # Skip if already exists (restart-safe)
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return {"id": image_id, "status": "skipped"}

        url = self.config.download_url(image_id)

        try:
            response = session.get(url, timeout=self.config.request_timeout, stream=True)
            response.raise_for_status()

            # Write atomically: write to temp, then rename
            temp_path = dest_path.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            temp_path.rename(dest_path)
            return {"id": image_id, "status": "downloaded"}

        except requests.RequestException as e:
            logger.debug("Download failed for ID %s: %s", image_id, e)
            # Clean up partial temp file
            temp_path = dest_path.with_suffix(".tmp")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return {"id": image_id, "status": "failed", "error": str(e)}

    def download(self, image_ids: List[str]) -> DownloadStats:
        """
        Download images concurrently using a thread pool.

        Args:
            image_ids: List of Picsum image IDs to download.

        Returns:
            DownloadStats with counts and timing.
        """
        self.config.ensure_dirs()
        self.stats = DownloadStats(total_requested=len(image_ids))

        logger.info(
            "Starting bulk download: %d images, %d workers, %dx%d resolution",
            len(image_ids),
            self.config.max_workers,
            self.config.image_width,
            self.config.image_height,
        )

        start_time = time.perf_counter()
        session = self._build_session()

        try:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {
                    executor.submit(self._download_single, session, img_id): img_id
                    for img_id in image_ids
                }

                with tqdm(
                    total=len(image_ids),
                    desc="Downloading",
                    unit="img",
                    ncols=100,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                ) as pbar:
                    for future in as_completed(futures):
                        result = future.result()
                        status = result["status"]

                        if status == "downloaded":
                            self.stats.downloaded += 1
                        elif status == "skipped":
                            self.stats.skipped += 1
                        elif status == "failed":
                            self.stats.failed += 1
                            self.stats.failed_ids.append(result["id"])

                        pbar.update(1)
                        pbar.set_postfix(
                            ok=self.stats.downloaded,
                            skip=self.stats.skipped,
                            fail=self.stats.failed,
                        )

        finally:
            session.close()

        self.stats.elapsed_seconds = time.perf_counter() - start_time

        # Log failures to disk
        if self.stats.failed_ids:
            self._write_failure_log()

        return self.stats

    def _write_failure_log(self) -> None:
        """Write failed image IDs to disk for manual retry."""
        log_path = self.config.output_dir / self.config.failed_log
        with open(log_path, "w", encoding="utf-8") as f:
            for failed_id in self.stats.failed_ids:
                f.write(f"{failed_id}\n")
        logger.info(
            "Wrote %d failed IDs to %s",
            len(self.stats.failed_ids),
            log_path,
        )
