# Architecture Decision Record (ADR)

## ADR 0001: Asynchronous Event-Driven Ingestion & Polymorphic Media Schema

* **Status**: Accepted
* **Date**: 2026-06-26
* **Author**: Technical Lead / Architect

---

## 1. Context & Problem Statement
The PhotoMind AI system needs to ingest heavy media assets (photos, and in the future, videos, documents, and audio clips). Processing these assets synchronously during HTTP upload (e.g., resizing thumbnails, parsing EXIF metadata, calculating hashes) degrades response latency, threatens web server availability under load, and risks connection timeouts. Furthermore, setting a static database structure specialized only for photos limits expansion into other media types.

---

## 2. Proposed Decisions

### A. Asynchronous Event-Driven Pipeline
Decouple asset ingestion into a fast synchronous gateway phase and a decoupled asynchronous processing phase:
* **Synchronous (Fast-Ingest)**: Upload Service reads the multipart stream, computes the SHA-256 hash on-the-fly, validates file headers, writes the original binary file, records the database state as `UPLOADED`, queues a background processing task, and returns the asset UUID immediately to the client.
* **Asynchronous (Background)**: The task worker consumes the task, shifts the asset status to `PROCESSING`, performs metadata extraction and thumbnail scaling, writes outputs to storage/database, and updates status to `READY` (or `FAILED` if errors trigger retries exhaustively).

### B. Polymorphic Media Database Schema
Utilize a parent-child database model:
* **Parent Table (`media_assets`)**: Stores common parameters (UUID, filename, hash, media type, status, paths, size).
* **Type-Specific Tables (e.g. `photo_metadata`, `video_metadata`)**: Stores specific attributes. A unique foreign key references the parent record.

### C. Processing Worker and Micro-Services
Extract logic into dedicated single-responsibility interfaces:
* **Upload Service**: Handles the raw multipart payload.
* **Storage Service**: Handles physical writes/reads to the filesystem.
* **Hashing Service**: Calculates SHA-256 for deduplication.
* **Thumbnail Service**: Handles resizing/encoding WebP formats.
* **Metadata Service**: Extracts structural metadata details.
* **Processing Worker**: Coordinates tasks, state transitions, and retry logic.

---

## 3. Alternatives Considered

* **Synchronous Processing**: Block the request thread until the thumbnail and EXIF data are generated.
  * *Verdict*: Rejected. Unscalable, highly susceptible to web request timeouts, and creates poor user experience.
* **Single Table Inheritance (No parent-child split)**: Put all metadata fields into one flat `photos` table.
  * *Verdict*: Rejected. Creates wide tables with mostly `NULL` values when expanded to document, video, or audio media assets.

---

## 4. Consequences
* **Pros**:
  * Response times are flat (< 100ms) regardless of image resolution.
  * Extensible design supports documents and video storage out of the box.
  * Processing failures don't block upload success; users receive intermediate statuses (`PROCESSING` or `FAILED`).
  * Web event loops are protected from CPU-bound starvation.
* **Cons**:
  * Added complexity in database state tracking (requires polling or websockets on the frontend to update status).
  * System requires running message workers alongside APIs (increased container resource count).
