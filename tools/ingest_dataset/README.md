# PhotoMind AI — Dataset Ingestion Pipeline

A production-grade dataset ingestion script designed to recursively scan a target directory, extract image quality and metadata attributes, compute vector embeddings, index them in Qdrant, and persist record profiles inside PostgreSQL asynchronously.

## Features

| Feature | Details |
|---|---|
| **Batch Processing** | Processes groups of images concurrently using asyncio to optimize CPU-bound steps and network calls |
| **Duplicates Check** | Computes SHA-256 file hashes to skip already ingested files, making the script completely restart-safe |
| **Perceptual Hashing** | Calculates a 64-bit difference hash (dHash) to locate near-identical copies of photos |
| **Quality Analysis** | Measures blur, brightness, darkness, and sharpness, and flags UI screenshots using aspect ratio / resolution heuristics |
| **CLIP Indexing** | Generates 512-dimension vector embeddings using the local CLIP model, indexed dynamically into Qdrant |
| **Retry Resilience** | Implements robust retry mechanisms with exponential backoff on model inference failures |
| **Audit Logging** | Outputs all operations and lifecycle timestamps to `logs/ingest.log` |
| **Manifest Summary** | Produces a `manifest.json` report containing final ingestion statistics |

## Installation

```bash
cd tools/ingest_dataset
pip install -r requirements.txt
```

## Usage

Ensure Docker containers are running. Run the command from the **project root** directory:

```bash
# Default ingestion (processes dataset/photomind_v1/)
python -m tools.ingest_dataset.main

# Custom dataset folder and batch size configuration
python -m tools.ingest_dataset.main --dataset dataset/my_images_v1 --batch-size 20

# Ingest without generating CLIP embeddings (Qdrant)
python -m tools.ingest_dataset.main --skip-embeddings

# Ingest without computing quality analysis
python -m tools.ingest_dataset.main --skip-quality

# Verbose debugging logs printed to standard output
python -m tools.ingest_dataset.main -v
```

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--dataset` | `dataset/photomind_v1` | Target directory to scan recursively |
| `--batch-size` | `10` | Concurrency batch size for processing |
| `--workers` | `4` | Concurrency limits for embedding steps |
| `--skip-embeddings`| — | Skip CLIP generation and Qdrant indexing |
| `--skip-gemini` | — | Skip Gemini description generation |
| `--skip-quality` | — | Skip calculating blur, brightness, and sharpness |
| `-v`, `--verbose` | — | Enable debug logging output to console |

## Integration & Database Storage

### PostgreSQL Records
- **`media_assets`**: Stores general info (SHA-256 hash, size, storage paths, status).
- **`photo_metadata`**: Stores dimensions and EXIF metadata (make, model, exposure, aperture, ISO, GPS coordinates).
- **`media_embeddings`**: Keeps track of CLIP model indexing.
- **`image_ai_analysis`**: Stores text caption descriptions and packs quality metrics/pHash into the JSON `keywords` column.

### Qdrant Vector DB
- CLIP embeddings are stored inside version-specific collections (e.g. `media_embeddings_clip_vit_b_32`), populated with payload descriptors pointing back to the asset UUID.

## Directory Logs & Manifests

Upon completion, the script generates:
- **`logs/ingest.log`**: Standard output logs with timing and processing states.
- **`<dataset_dir>/manifest.json`**:
```json
{
  "total_images": 500,
  "imported": 482,
  "duplicates_skipped": 18,
  "failed": 0,
  "completed_at": "2026-07-06T13:42:00Z",
  "processing_time_seconds": 12.35
}
```
