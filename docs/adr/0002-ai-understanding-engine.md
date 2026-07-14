# Architecture Decision Record (ADR)

## ADR 0002: AI Understanding Engine — Provider Abstraction

* **Status**: Accepted
* **Date**: 2026-07-14
* **Sprint**: Sprint 5
* **Author**: Technical Lead / Architect

---

## 1. Context & Problem Statement

PhotoMind AI is evolving from a photo gallery into a **Local-First AI Memory Operating System**.
A key capability of a memory OS is understanding the *content* of every image — not just its
pixel embedding, but structured semantic knowledge: what is in the image, who is in it, where
it was taken, what event it captures, and how it connects to the user's life.

This requires calling a vision AI model for every uploaded image. The challenge is:

* **Model lock-in**: If the codebase calls `google.genai` directly, switching to GPT-4V,
  Claude Vision, Florence, or any local model requires touching every file that imports it.
* **Testing complexity**: Tests that depend on real AI providers are slow, fragile,
  and require network access and API keys.
* **Non-blocking uploads**: Vision model calls take 1–5 seconds. They must never block
  the upload response or the CLIP embedding pipeline.
* **Graceful degradation**: If no API key is configured, the system must continue working
  normally — uploads succeed, CLIP search works, gallery loads — with AI analysis simply marked
  as skipped.

---

## 2. Proposed Decisions

### A. VisionProvider Abstraction

Introduce a `VisionProvider` abstract base class that all vision model implementations must satisfy:

```python
class VisionProvider(ABC):
    async def analyze(image_path: str) -> Optional[AnalysisResult]: ...
    def get_model_name() -> str: ...
    def get_model_version() -> str: ...
```

`AnalysisResult` is a normalized dataclass with all possible output fields.
Every concrete provider maps its API response into this structure.

**Benefit**: `AIAnalysisService` and `worker.py` depend only on `VisionProvider`.
They are completely unaware of Gemini, GPT-4V, or any specific model.

### B. AIAnalysisService — Single-Responsibility Orchestrator

A dedicated `AIAnalysisService` class handles the full analysis lifecycle:

```
MediaAsset (READY)
    ↓
Select VisionProvider
    ↓
provider.analyze(image_path)
    ↓  None → SKIPPED_NO_PROVIDER
    ↓  AnalysisResult → validate → upsert ImageAIAnalysis → COMPLETED
    ↓  Exception → FAILED + retry_count + error_message
```

The service is injected with a provider at construction time, making it trivially testable
with mock providers (no API calls, no network, no credentials).

### C. Provider Factory — Centralized Selection

`get_default_provider()` reads `settings.VISION_PROVIDER` and returns the correct
implementation. Adding a new provider requires only:

1. A new file implementing `VisionProvider`
2. A new `elif` branch in `provider_factory.py`

Nothing else changes.

### D. Fire-and-Forget Background Task

After a `MediaAsset` reaches `READY` status in `worker.py`, the AI analysis is
enqueued as a detached asyncio task:

```python
asyncio.create_task(run_ai_analysis_task(asset_id))
```

This means:
* Uploads remain fast (< 100ms response)
* CLIP-based search is available immediately after READY
* AI analysis runs in the background, updating the Knowledge Record asynchronously

### E. Extended Knowledge Record — ImageAIAnalysis

The existing `image_ai_analysis` table is extended with all required fields using
additive-safe `ALTER TABLE ... ADD COLUMN` semantics (via SQLAlchemy `create_all`).
New columns default to `NULL`. Existing rows remain valid.

A new `AnalysisStatus` enum tracks the lifecycle:
`PENDING → PROCESSING → COMPLETED | FAILED | SKIPPED_NO_PROVIDER`

---

## 3. Alternatives Considered

### Direct Gemini Integration
Call `google.genai` directly from the worker or a service.

*Verdict*: Rejected. Creates vendor lock-in. Every provider switch requires editing
multiple files. Testing requires real API credentials. Violates the Memory OS vision
of being model-agnostic.

### Celery / Redis Task Queue
Use a dedicated task queue for AI analysis.

*Verdict*: Deferred. The current architecture uses FastAPI background tasks and
`asyncio.create_task()`, which is sufficient for the current scale. A Celery queue
can be introduced without changing the `VisionProvider` abstraction if volume demands it.

### Synchronous Analysis During Upload
Block the upload response until AI analysis completes.

*Verdict*: Rejected. Vision model calls take 1–5 seconds. Blocking the HTTP response
degrades UX and risks timeouts. The ingestion pipeline already uses the async pattern.

### One Table Per Provider
Store Gemini results in `gemini_analysis`, GPT-4 results in `gpt4_analysis`, etc.

*Verdict*: Rejected. Complicates queries across the application. The normalized
`ImageAIAnalysis` + `AnalysisResult` abstraction provides a single query surface
regardless of which provider generated the data.

---

## 4. How to Add a Future Provider

1. Create `backend/app/modules/media/services/ai_analysis/gpt4v_provider.py`
2. Implement `class GPT4VisionProvider(VisionProvider)`
3. Implement `analyze()` mapping OpenAI response → `AnalysisResult`
4. Add to `provider_factory.py`:
   ```python
   elif provider_name == "gpt4v":
       return GPT4VisionProvider()
   ```
5. Set `VISION_PROVIDER=gpt4v` in `.env`

**Zero changes** to `AIAnalysisService`, `worker.py`, `models.py`, or the frontend.

---

## 5. Consequences

### Pros
* **Model-agnostic**: The architecture supports Gemini, GPT-4V, Claude, Florence, Qwen-VL,
  and any future model with no changes to business logic.
* **Testable**: Mock providers enable fast, isolated unit tests with no external dependencies.
* **Non-blocking**: Uploads remain fast; CLIP search is immediately available after READY.
* **Graceful degradation**: Missing API key → SKIPPED_NO_PROVIDER; system continues normally.
* **Auditable**: `model_name`, `model_version`, `processed_at`, `raw_response` fields
  provide a complete audit trail per Knowledge Record.
* **Extensible schema**: `ImageAIAnalysis` supports all requested fields and is designed
  for future additions without migrations.

### Cons
* **Eventual consistency**: AI analysis results are not available at upload time.
  The frontend must handle `PENDING` / `PROCESSING` states.
* **No retry scheduling**: FAILED records are flagged for retry but there is no
  automatic scheduler yet. Sprint 6+ will add a retry queue.

---

## 6. References

* [ADR 0001 — Async Event-Driven Ingestion](./0001-async-event-driven-ingestion.md)
* `backend/app/modules/media/services/ai_analysis/` — implementation
* `backend/app/modules/media/models.py` — `ImageAIAnalysis`, `AnalysisStatus`
* `backend/app/modules/media/worker.py` — background task integration
