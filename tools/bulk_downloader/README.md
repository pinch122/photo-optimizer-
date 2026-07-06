# PhotoMind AI — Bulk Image Downloader

A production-grade, concurrent image downloader that generates large datasets from the [Lorem Picsum](https://picsum.photos) API for testing PhotoMind AI pipelines.

## Features

| Feature | Details |
|---|---|
| **High Throughput** | ThreadPoolExecutor with 20–50 configurable workers |
| **Restart-Safe** | Skips already-downloaded files automatically |
| **Deduplicated** | Downloads by image ID, preventing duplicate fetches |
| **Retry Logic** | Exponential backoff with configurable retry attempts |
| **Atomic Writes** | Writes to `.tmp` then renames, preventing partial files |
| **Progress Bar** | Real-time tqdm progress with download/skip/fail counters |
| **Failure Logging** | Writes failed IDs to `failed_downloads.txt` for retry |
| **Configurable** | Resolution, workers, count, timeout, output directory |
| **Statistics** | Prints download counts, success rate, and elapsed time |

## Installation

```bash
cd tools/bulk_downloader
pip install -r requirements.txt
```

## Usage

Run from the **project root** directory:

```bash
# Download 10,000 images (default)
python -m tools.bulk_downloader.main

# Download 500 images at 1920x1080
python -m tools.bulk_downloader.main --count 500 --width 1920 --height 1080

# Download 1,000 images with 50 workers
python -m tools.bulk_downloader.main --count 1000 --workers 50

# Custom output directory
python -m tools.bulk_downloader.main --output ./test_images --count 200

# Verbose debug logging
python -m tools.bulk_downloader.main --count 100 -v
```

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--count` | `10000` | Number of images to download (1–100,000) |
| `--width` | `1024` | Image width in pixels |
| `--height` | `768` | Image height in pixels |
| `--workers` | `30` | Concurrent download threads (1–50) |
| `--output` | `downloaded_images` | Output directory path |
| `--retries` | `3` | Max retry attempts per failed image |
| `--timeout` | `30` | HTTP request timeout in seconds |
| `-v` | — | Enable debug-level logging |

## Architecture

```
tools/bulk_downloader/
├── __init__.py         # Package marker
├── config.py           # Configuration dataclass (all settings)
├── client.py           # Picsum API client (pagination, deduplication)
├── downloader.py       # ThreadPoolExecutor download engine
├── main.py             # CLI entry point (argparse, logging, phases)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

### Execution Flow

```
Phase 1: Metadata Collection
  └─ Paginate Picsum /v2/list API
  └─ Collect unique image IDs
  └─ Cap at --count limit

Phase 2: Concurrent Downloads
  └─ ThreadPoolExecutor (--workers threads)
  └─ Skip existing files (restart-safe)
  └─ Retry failures with exponential backoff
  └─ Atomic write: .tmp → .jpg rename
  └─ tqdm progress bar

Phase 3: Statistics & Reporting
  └─ Print download/skip/fail counts
  └─ Log failed IDs to failed_downloads.txt
  └─ Report elapsed time and success rate
```

## Output

Images are saved as `<image_id>.jpg` in the output directory:

```
downloaded_images/
├── 0.jpg
├── 1.jpg
├── 10.jpg
├── 100.jpg
├── 1000.jpg
├── ...
└── failed_downloads.txt  (only if failures occurred)
```

## Use Cases in PhotoMind AI

This dataset is designed for testing:

- **Duplicate Detection** — SHA-256 hashing across identical downloads
- **CLIP Embeddings** — Generating vector representations at scale
- **Vector Search** — Populating Qdrant with thousands of image vectors
- **Semantic Search** — Natural language queries against large photo libraries
- **OCR Pipeline** — Text extraction from diverse image content
- **Image Quality Analysis** — Resolution, compression, and format validation

## Resuming Interrupted Downloads

Simply re-run the same command. The downloader automatically skips images that already exist on disk:

```bash
# First run (interrupted at 3,000 images)
python -m tools.bulk_downloader.main --count 10000

# Resume — skips the 3,000 already downloaded
python -m tools.bulk_downloader.main --count 10000
```

## Retrying Failures

After a session completes, check `downloaded_images/failed_downloads.txt` for IDs that failed. Re-running the downloader will automatically retry these since the files don't exist on disk.
