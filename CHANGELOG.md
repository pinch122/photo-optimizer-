# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-06-26

### Added
* **AI Embedding Pipeline**: Asynchronous 512-dimension vector calculation using local CLIP (`clip-ViT-B-32`) models.
* **Qdrant Vector Database Integration**: Automated Cosine similarity index creation and idempotent vector point upserts/deletes.
* **Vector-Model Versioning**: Created a `media_embeddings` table to isolate embedding models and collections, facilitating future model upgrades.
* **Reprocessing API Route**: Exposed `POST /media/{id}/reprocess` to delete child database records and force background vector re-calculations.
* **Safe Rollbacks**: Integrated database rollback triggers to delete vector points from Qdrant if database commits abort.
* **Offline Testing Mocks**: Configured `MockSentenceTransformer` and Qdrant in-memory client for rapid, internet-independent test suite execution.

---

## [0.1.0] - 2026-06-26

### Added
* **Asynchronous Ingestion Pipeline**: Decoupled HTTP uploads from media processing.
* **Polymorphic Database Schema**: Implemented extensible SQLAlchemy schema supporting `media_assets` and `photo_metadata`.
* **Magic Bytes Validation**: Added validation of binary signatures for security.
* **SHA-256 Deduplication**: Added instant duplicate upload checks.
* **Thumbnail Generation**: Added auto-rotating, center-weighted WebP scaling.
* **EXIF Parser**: Added EXIF tag and GPS DMS-to-decimal degree conversion.
* **Local Storage Partitions**: Mapped files under date-partitioned storage directories (`originals/YYYY/MM/`).
* **FastAPI Lifespan Context Manager**: Added modern lifespan app management.
* **Test Isolation**: Configured in-memory SQLite and Qdrant database tests.

### Fixed
* Refactored all synchronous writes to non-blocking async `anyio` streams.
* Resolved warning messages related to Pydantic v2 `ConfigDict` schemas.
* Streamlined worker SQL session lifespans.
