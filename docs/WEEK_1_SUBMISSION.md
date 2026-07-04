# Week 1 Submission — Pinchu Alok — E2

## 1. Project Repository
- **GitHub Repository**: https://github.com/pinch122/photo-optimizer-

---

## 2. Project Information
- **Project Name**: PhotoMind AI
- **One-line Description**: A personal AI memory assistant that indexes and searches photo libraries using natural language semantic text queries.
- **Problem Statement Code**: E2
- **Segment Name**: AI & Fullstack Engineering
- **Name**: Pinchu Alok
- **Target Roles**: Fullstack Developer / AI Engineer / Software Engineer Intern

---

## 3. README Checklist
- [x] Project name (`PhotoMind AI`)
- [x] One-line description
- [x] Problem statement code
- [x] Segment name
- [x] Candidate name (`Pinchu Alok`)
- [x] Target roles
- [x] Installation guide (Local & Docker instructions)
- [x] Features overview
- [x] API documentation (REST endpoints specification)
- [x] Docker Compose setup details

---

## 4. Initial Architecture
```
┌───────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                    │
└─────────────────────────────┬─────────────────────────────┘
                              │ HTTP REST / JSON
                              ▼
┌───────────────────────────────────────────────────────────┐
│                    FastAPI Backend API                    │
└──────────────────┬───────────────────────────┬────────────┘
                   │ SQL Queries               │ Vectors
                   ▼                           ▼
┌─────────────────────────────┐ ┌───────────────────────────┐
│   PostgreSQL DB Engine      │ │    Qdrant Vector DB       │
│  (Asset metadata & EXIF)    │ │    (CLIP Vector index)    │
└─────────────────────────────┘ └───────────────────────────┘
```

### Data & Retrieval Flow:
1. **Frontend (Next.js)** captures upload streams or user search strings.
2. **FastAPI Backend** acts as the ingestion controller and search coordinator.
3. **PostgreSQL** stores structured relational metadata (resolution, timestamps, file attributes, EXIF parameters).
4. **Qdrant** indexes raw 512-dimension visual/textual vectors.
5. **CLIP ViT-B-32** generates vector representations on CPU during ingest and search.
6. **Semantic Search API** executes cosine similarity lookups against Qdrant, hydrates metadata from PostgreSQL, and returns ranked results.

---

## 5. Tech Stack Table

| Component | Choice | Why |
|---|---|---|
| **Frontend** | Next.js 15 | App Router, RSC support, dynamic styling, fast client routing. |
| **Backend** | FastAPI | Async I/O, auto OpenAPI/Swagger docs, high performance, Pydantic validation. |
| **Language** | Python + TypeScript | Python for AI pipeline (CLIP, PyTorch); TypeScript for type-safe frontend. |
| **Database** | PostgreSQL | ACID compliance, relational joins for metadata, industry-standard stability. |
| **Vector DB** | Qdrant | Fast HNSW indexes, HTTP/gRPC interfaces, high-concurrency queries, dashboard. |
| **AI Model** | CLIP ViT-B-32 | Lightweight multi-modal model, 512-dim embeddings, runs on CPU. |
| **ORM** | SQLAlchemy | Async queries, eager relationship loading, mature toolkit. |
| **Styling** | Tailwind CSS | Utility-first, fast styling, dark-mode support. |
| **Containerization** | Docker Compose | Multi-container orchestration, isolated networking, volume config. |
| **API Client** | Axios | Configurable timeouts, interceptors, simple JSON handling. |
| **State Management** | TanStack React Query | Server-state caching, polling, optimistic updates. |

---

## 6. Data Layer Working

- **Image Ingest**: Multi-part stream ingestion, signature calculation, file writing to disk.
- **Relational Storage**: EXIF metadata (camera make, ISO, location) extracted and stored in PostgreSQL.
- **Duplicate Prevention**: SHA-256 hashing rejects duplicate uploads with `409 Conflict`.
- **Background Pipeline**: Non-blocking workers extract parameters and generate WebP thumbnails.
- **Vector Calculations**: CLIP generates L2-normalized 512-dim vectors from queries.
- **Vector Indexing**: Embeddings stored in Qdrant collections.
- **Ranked Search**: Top-K vector neighbors fetched from Qdrant, joined with PostgreSQL records, sorted.
- **System Health**: Health check routes verify DB connectivity.
- **Docker Orchestration**: Single-command launch via `docker compose up -d`.

**Proof:**

![Data ingestion terminal output](docs/screenshots/ingest_success.png)
![PostgreSQL table with metadata](docs/screenshots/db_query.png)
![Semantic search results in Qdrant](docs/screenshots/search_results.png)

---

## 7. Git Progress
Repository has **10+ commits** on the main branch, following Conventional Commits standard (`feat(infra): ...`, `fix(infra): ...`, `feat(frontend): ...`).

---

## 8. Friday Demo
Loom Video: <ADD LOOM LINK>

---

## 9. One Page Status

### What's Done
- Backend endpoints complete: upload, status, reprocessing, detail fetch, semantic search
- Docker Compose fully configured with Qdrant health checks
- PostgreSQL migrations + async schema integration
- Qdrant vector collection indexing operational
- CLIP embedding pipeline running on CPU
- Duplicate detection via hashing
- Async ingestion workers (metadata parsing + thumbnails)
- Frontend scaffold: Next.js 15, sidebar nav, mobile nav, dark theme
- Core pages built: Dashboard, Upload, Gallery, Search, Settings, Analytics, Collections

### What's Stuck
- Gallery thumbnail rendering on custom aspect ratios
- Mobile grid alignment tweaks
- Smoother skeleton loading transitions
- Duplicate-upload alert banner polish

### Next Week Goals
1. Polish frontend UI, fix gallery aspect ratio rendering, improve skeleton loaders
2. Enhance semantic search UI with score breakdown cards, detail previews, metadata filters
3. Move to staging/production build config, clean up repo, prepare final demo video
