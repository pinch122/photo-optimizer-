# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
