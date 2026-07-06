"""
Lorem Picsum API client for fetching image metadata via pagination.

Handles rate limiting, retries, and deduplication of image IDs.
"""

import time
import logging
from typing import List, Dict, Any, Set

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DownloaderConfig

logger = logging.getLogger("bulk_downloader.client")


class PicsumClient:
    """HTTP client for the Lorem Picsum v2 listing API."""

    def __init__(self, config: DownloaderConfig) -> None:
        self.config = config
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Create a requests session with connection pooling and automatic retries."""
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

    def fetch_image_ids(self) -> List[str]:
        """
        Paginate through the Picsum listing API and collect unique image IDs.

        Returns:
            A deduplicated list of image ID strings, capped at config.max_images.
        """
        collected_ids: List[str] = []
        seen: Set[str] = set()
        page = 1

        logger.info(
            "Starting metadata fetch from %s (target: %d images)",
            self.config.list_url,
            self.config.max_images,
        )

        while len(collected_ids) < self.config.max_images:
            try:
                response = self.session.get(
                    self.config.list_url,
                    params={"page": page, "limit": self.config.page_size},
                    timeout=self.config.request_timeout,
                )
                response.raise_for_status()
                items: List[Dict[str, Any]] = response.json()

                if not items:
                    logger.info("No more pages available at page %d. Ending pagination.", page)
                    break

                for item in items:
                    image_id = str(item.get("id", ""))
                    if image_id and image_id not in seen:
                        seen.add(image_id)
                        collected_ids.append(image_id)
                        if len(collected_ids) >= self.config.max_images:
                            break

                logger.info(
                    "Page %d: fetched %d items, total collected: %d",
                    page, len(items), len(collected_ids),
                )
                page += 1

            except requests.RequestException as e:
                logger.warning("Failed to fetch page %d: %s. Retrying after delay...", page, e)
                time.sleep(self.config.retry_delay_base * 2)

        logger.info("Metadata collection complete. Total unique IDs: %d", len(collected_ids))
        return collected_ids

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()
