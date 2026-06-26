# PhotoMind AI – Multimodal Personal Memory Assistant

PhotoMind AI is a production-grade personal memory assistant designed to help users intelligently search, organize, optimize, and interact with their media gallery using natural language processing, computer vision, and large language models (LLMs). It prioritizes user privacy and localized high-performance indexing.

---

## Architecture Blueprint

```
[Public Gateway / Reverse Proxy (e.g., NGINX / Traefik)]
       |
       +-------> [Frontend Interface (Next.js / React)]
       |
       +-------> [API Gateway Gateway (FastAPI)]
                   |
                   | (Private Internal Virtual Network Subnet)
                   v
         +---------+---------+
         |                   |
         v                   v
   [PostgreSQL]          [Qdrant]
 (Relational DB)       (Vector DB)
```

> [!IMPORTANT]
> **Network Security Boundary**: In production deployments, only the **Frontend Client UI** and the **FastAPI Gateway Endpoint** are exposed to the public internet. Relational databases (PostgreSQL), vector indexes (Qdrant), and CPU-bound task workers operate exclusively inside isolated virtual private networks and cannot be queried externally.

---

## Features

### Core Capabilities
* **Asynchronous Media Ingest Pipeline**: Decoupled HTTP uploads from heavy processing. Accepts single and batch image files, performs file magic-byte validation, and registers files with status `UPLOADED`.
* **Perceptual WebP Thumbnails**: Automatically parses EXIF rotation standards, center-crops, and outputs WebP thumbnails.
* **EXIF & GPS Parsing**: Extracts metadata tags and parses rational DMS coordinates into float Decimal Degrees.
* **CLIP Vector Indexing**: Generates normalized 512-dimension vector representations locally using `clip-ViT-B-32` model architectures.
* **Idempotent Vector Upserting**: Indexes points in Qdrant collections mapped to model names.
* **Force Reprocessing**: Provides endpoints to clear child metadata, clean up thumbnails, and re-enqueue assets.

### Scheduled Roadmap
* **Sprint 3**: Storage optimization heuristics (Laplacian blur thresholds, brightness, perceptual hashing for duplicates).
* **Sprint 4**: AI Classification & OCR (Receipts, memes, documents, text search).
* **Sprint 5**: Multimodal Gallery Chat (RAG integration via Gemini API).

---

## Technology Stack

* **Backend Gateway**: FastAPI, Uvicorn, SQLAlchemy (Async), Pydantic v2, Pillow, SentenceTransformers (PyTorch).
* **Vector Database**: Qdrant (Cosine distance vector index).
* **Relational Database**: PostgreSQL.
* **Frontend Web Dashboard**: Next.js (App Router), React, TypeScript.
* **DevOps**: Docker, Docker Compose, GitHub Actions.

---

## Repository File Tree

```
photo-optimizer/
├── docker-compose.yml       # Infrastructure orchestration blueprint
├── .env.example             # Template configurations
├── .gitignore               # Ignored build configurations
├── README.md                # Technical blueprint
├── CHANGELOG.md             # Project release history
├── docs/                    # Architectural documents
│   └── adr/                 # Architecture Decision Records
│       └── 0001-async-event-driven-ingestion.md
├── backend/                 # FastAPI Service
│   ├── Dockerfile
│   ├── main.py              # Application lifecycle entry
│   ├── requirements.txt     # Python dependency lists
│   ├── pytest.ini           # Testing environments configurations
│   ├── app/                 # Backend core application
│   │   ├── config.py        # Settings loader
│   │   ├── database.py      # Persistence configurations
│   │   └── modules/
│   │       └── media/       # Media module logic boundary
│   └── tests/               # Standalone pytest suites
├── frontend/                # Next.js Client
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
└── storage/                 # Mapped files persistence (Git-ignored)
    ├── originals/           # Raw uploads
    ├── thumbnails/          # Compressed WebP items
    └── logs/                # Rotated logger traces
```

---

## Development Setup

### 1. Configure Local Environment Variables
Copy the template configuration file in the project root:
```bash
cp .env.example .env
```
Populate parameters inside `.env` (a local database is spun up automatically, so you can leave default database credentials):
```env
ENV_MODE=development
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Boot local Docker Compose Stack
Compile and launch the multi-container development environment:
```bash
docker compose up --build
```

### 3. Local Endpoint Mappings
During development, the following ports are mapped to `localhost`:
* **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
* **Backend API Gateway**: [http://localhost:8000](http://localhost:8000)
* **Interactive API Playground**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Vector DB Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
* **Database Endpoint**: `localhost:5432`

---

## Production Deployment

### 1. Production Network Settings
For production, the host port mappings for internal database instances are removed from `docker-compose.yml` to prevent external port scans:
* Remove `5432:5432` mapping from `db` service.
* Remove `6333:6333` and `6334:6334` mapping from `qdrant` service.

### 2. Gateway Proxy Setup (NGINX Example)
Place the application behind a reverse proxy handling SSL certificates:
```nginx
# Serve Frontend
server {
    server_name my-gallery.example.com;
    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
    }
}

# Serve API Gateway
server {
    server_name api-gallery.example.com;
    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        client_max_body_size 50M; # Support large image batches
    }
}
```

### 3. Production Endpoint Mappings (Placeholders)
Configure client applications to interact strictly with public-facing SSL subdomains:
* **Frontend Client Interface**: `https://my-gallery.example.com`
* **Backend API Endpoint**: `https://api-gallery.example.com`

---

## API Documentation

### Media Upload
* **HTTP Method**: `POST`
* **Path**: `/api/media/upload`
* **Request Format**: `multipart/form-data` containing `file` binary.
* **Statuses**:
  * `201 Created`: Asset is registered as `UPLOADED` and queued.
  * `409 Conflict`: SHA-256 hash match detected (duplicate file).

### Media Status
* **HTTP Method**: `GET`
* **Path**: `/api/media/{id}/status`
* **Response**: Returns asset lifecycle state (`UPLOADED`, `PROCESSING`, `READY`, `FAILED`).

### Media Metadata
* **HTTP Method**: `GET`
* **Path**: `/api/media/{id}`
* **Response**: Returns full coordinates, dimensions, camera configs, and database references.

### Serving Media Files
* **HTTP Method**: `GET`
* **Path**: `/api/media/{id}/file`
* **Query Params**: `size=original` or `size=thumbnail`.
* **Response**: Streams target binary formats.

### Reprocessing API
* **HTTP Method**: `POST`
* **Path**: `/api/media/{id}/reprocess`
* **Response**: Reset status to `UPLOADED`, cleans up file directories, and indexes vector points again.

---

## License
Distributed under the MIT License. See `LICENSE` for more information (to be added post-MVP).
