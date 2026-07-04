# Week 1 Submission — Pinchu Alok — E2

## 1. Project Repository
- **GitHub Repository**: <ADD REPO LINK> (https://github.com/pinch122/photo-optimizer-.git)

---

## 2. Project Information
- **Project Name**: PhotoMind AI
- **One-line Description**: A personal AI memory assistant that index and search photo libraries using natural language semantic text queries.
- **Problem Statement Code**: <PROBLEM_CODE>
- **Segment Name**: AI & Fullstack Engineering
- **Name**: Pinchu Alok
- **Target Roles**: Fullstack Developer / AI Engineer / Software Engineer Intern

---

## 3. README Checklist
I confirm that the project README contains all the following required details:
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
The initial architecture of the PhotoMind AI platform is detailed below. The **C4 Level 1 Architecture Diagram** is embedded and viewable directly within the repository README.md.

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
3. **PostgreSQL** stores structured relational metadata (resolution, timestamps, file attributes, and EXIF parameters).
4. **Qdrant** indexes raw 512-dimension visual/textual vectors.
5. **CLIP ViT-B-32** generates vector representations on CPU during ingest processing and search queries.
6. **Semantic Search API** executes Cosine similarity lookups against Qdrant, hydrates metadata records from PostgreSQL, and returns ranked results.

---

## 5. Tech Stack Table

| Component | Choice | Why |
|---|---|---|
| **Frontend** | Next.js 15 | App Router structure, React Server Components (RSC) capabilities, dynamic styling support, and fast client routing. |
| **Backend** | FastAPI | Async IO endpoints, automatic OpenAPI/Swagger docs, high performance, and Pydantic-based payload serialization. |
| **Language** | Python + TypeScript | Python for scientific computing/AI pipeline integration (CLIP, PyTorch) and TypeScript for type-safe interactive frontend. |
| **Database** | PostgreSQL | Robust ACID compliance, relation joins for EXIF metadata tables, and industry standard stability. |
| **Vector Database**| Qdrant | Fast HNSW vector indexes, clean HTTP/gRPC interfaces, high-concurrency query execution, and developer dashboard. |
| **AI Model** | CLIP ViT-B-32 | Lightweight multi-modal model generating unified 512-dimension text/image embeddings running efficiently on CPU. |
| **ORM** | SQLAlchemy | Robust Python SQL toolkit and Object-Relational Mapper supporting asynchronous queries and eager relationships. |
| **Styling** | Tailwind CSS | Utility-first CSS framework enabling rapid styling, custom themes, dark-mode flags, and design system constraints. |
| **Containerization**| Docker Compose | Multi-container setups, isolated networking, volume storage configurations, and simple orchestration. |
| **API Client** | Axios | Configurable timeouts, custom base headers, interceptor chains, and simple JSON integrations. |
| **State Management**| TanStack React Query| Asynchronous server-state caching, polling features, optimistic rendering, and simplified mutation workflows. |

---

## 6. Data Layer Working
We have successfully demonstrated and validated the end-to-end data layer lifecycle:
- **Image Ingest**: Multi-part stream ingestion, signature calculation, and file writing to disk.
- **Relational Storage**: Extraction of metadata (EXIF details, camera makes, ISO speeds, location markers) and insertion into PostgreSQL.
- **Duplicate Prevention**: SHA-256 hashing detects exact duplicate files, rejecting uploads with clean `409 Conflict` status.
- **Background Pipeline**: Non-blocking worker routines (FastAPI Background Tasks) extracting parameters and building WebP thumbnails.
- **Vector Calculations**: Tokenizing search strings and calculating L2-normalized 512-dimension vectors with CLIP.
- **Vector Indexing**: Storing embedding records in Qdrant collections.
- **Ranked Search**: Fetching top-K vector neighbors from Qdrant, query-joining records from PostgreSQL, and sorting results.
- **System Health**: Health check routes verifying database socket connectivity.
- **Docker Orchestration**: Standard launch configurations via single command `docker compose up -d`.

*Screenshots and CLI command outputs illustrating successful pytest evaluations, database tables, and Qdrant vector spaces are stored in the walkthrough repository log.*

---

## 7. Git Progress
The repository holds a complete development history with **more than five commits** on the main branch. Every commit follows the **Conventional Commits** standard (e.g. `feat(infra): ...`, `fix(infra): ...`, `feat(frontend): ...`).

---

## 8. Friday Demo
Loom Video:
<ADD LOOM LINK>

---

## 9. One Page Status

### What's Done
- **Backend Complete**: All endpoints for single upload, status checks, reprocessing, detail fetching, and semantic search are operational.
- **Docker Setup**: Fully configured `docker-compose.yml` with optimized multi-container networks and robust Qdrant TCP health checking.
- **Database Integration**: PostgreSQL migrations and schema tables fully connected with async drivers.
- **Qdrant Vector DB**: Vector collection indexing operational and integrated with Qdrant client APIs.
- **CLIP Embeddings**: Local embedding pipeline initialized on CPU-only dependencies to avoid timeouts.
- **Duplicate Identification**: Hashing checks successfully abort duplicate uploads.
- **Ingestion Workers**: Asynchronous metadata parsing and thumbnail generation functions.
- **Frontend Scaffold**: Next.js 15 workspace with layout components (collapsible sidebar navigation, mobile bottom navigation rail, and dark-theme configurations).
- **Core Interfaces**: Initial page views completed for:
  - Dashboard (Stats dashboard, counters, storage utilization).
  - Upload Page (Drag-and-drop area, queues, progress tracking, and toast alerts).
  - Gallery Page (Infinite-scroll image grids, sort configurations, and filters).
  - Search Page (Oversized search inputs, prompt suggestions, and local search history).
  - Settings, Analytics, and Collections views.

### What's Stuck
- **Gallery Thumbnail Renders**: Minor layout issues on custom asset aspect ratios.
- **UI Tweaks**: Fine-tuning grid alignment on mobile screens.
- **Loading Indicators**: Adding smoother skeleton transitions for dynamic card loading.
- **Duplicate Notifications**: Enhancing visual alert banners on file conflict bails.

### Next Week Goals
- **Goal 1**: Complete frontend UI polish, resolve layout aspect ratio rendering in gallery cells, and improve skeleton loaders.
- **Goal 2**: Enhance the semantic search UI with visible score breakdown cards, full detail preview popovers, and secondary metadata filters.
- **Goal 3**: Transition the application to standard staging/production build configurations, clean up residual files, and prepare the final demo video.
