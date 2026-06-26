# PhotoMind AI – Multimodal Personal Memory Assistant

PhotoMind AI is a production-grade personal memory assistant powered by natural language search, database indexing, computer vision, and large language models (LLMs). It runs locally in a containerized environment.

---

## System Architecture

```
                       +-----------------------+
                       |    Next.js Client     |
                       |     (Vanilla CSS)     |
                       +-----------+-----------+
                                   | HTTP / WebSockets
                                   v
                       +-----------------------+
                       |    FastAPI Gateway    |
                       +-----+-----+-----+-----+
                             |     |     |
      +----------------------+     |     +----------------------+
      | SQL / JSON                 | Vector                     | JSON / Images
      v                            v                            v
+------------------+         +------------------+         +------------------+
|  PostgreSQL DB   |         |    Qdrant DB     |         |    Gemini API    |
| (Metadata, Hash) |         | (CLIP Embeddings)|         | (Multimodal LLM) |
+------------------+         +------------------+         +------------------+
```

### Core Pipeline Design
* **Synchronous Gate**: Accepts upload, checks SHA-256 for duplicates, saves raw files, creates records with status `UPLOADED`, and queues background execution.
* **Asynchronous Workers**: Coordinates EXIF extraction, WebP thumbnail generation, and updates the asset state to `READY` or `FAILED`.

---

## Directory Structure

```
photo-mind-ai/
├── docker-compose.yml       # Production/development docker container compose stack
├── .env.example             # Configuration variables blueprint
├── .gitignore               # Excludes builds, local databases and storage folders
├── README.md                # System documentation
├── docs/                    # Architecture Decision Records (ADRs) and engineering specs
│   └── adr/
│       └── 0001-async-event-driven-ingestion.md
├── backend/                 # Python FastAPI service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/                 # FastAPI core implementation modules
│   └── tests/               # pytest suites
├── frontend/                # Next.js frontend client UI
│   ├── Dockerfile
│   ├── package.json
│   └── src/
└── storage/                 # Local directory mapping for persistent volumes (Git-ignored)
    ├── originals/
    ├── thumbnails/
    └── logs/
```

---

## Getting Started

### Prerequisites
* Docker and Docker Compose installed.
* Gemini API Key (obtained from Google AI Studio).

### Setup Environment
1. Clone this repository.
2. Copy the configuration template:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and configure your settings:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Start Services
Spin up the local containerized network:
```bash
docker compose up --build
```
Once initialized, the services will run at:
* **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
* **Backend API Gateway**: [http://localhost:8000](http://localhost:8000)
* **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## Engineering Standards

1. **SOLID Principles**: Maintain strict separations between Routing, Service Logic, Hashing, Formatting, and Persistence layers.
2. **Event Loop Safety**: Offload Pillow resizing, hash computations, and EXIF processing to thread pools.
3. **Database Integrity**: Execute atomic rollback operations. If the SQL query fails, remove the newly written binary assets.
4. **Code Quality**: Follow PEP 8 styles for Python. Implement structured log outputs (JSON log wrappers).
