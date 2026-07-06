# PhotoMind AI — Synthetic Dataset Generator

A production-grade tool that generates categorized synthetic image datasets from original source images for testing PhotoMind AI pipelines.

## Features

| Feature | Details |
|---|---|
| **7 Transform Types** | Duplicate, resize/compress, blur, darken, brighten, rotate, crop |
| **EXIF Preservation** | Embeds original EXIF data in transformed images where possible |
| **Restart-Safe** | Never overwrites existing files; resumes from last state |
| **Reproducible** | Optional `--seed` flag for deterministic dataset generation |
| **Progress Bars** | tqdm progress tracking per category with counts |
| **Manifest Output** | Writes `manifest.json` summarizing the full dataset |
| **~1,000 Images** | 500 originals + 500 transforms by default |
| **Production-Ready** | PEP8, type hints, docstrings, structured logging |

## Installation

```bash
cd tools/dataset_generator
pip install -r requirements.txt
```

## Prerequisites

Place your original images in the source directory:

```
dataset/
└── originals/
    ├── 0.jpg
    ├── 1.jpg
    ├── 10.jpg
    └── ... (500 images)
```

You can use the **Bulk Image Downloader** tool to populate this:

```bash
python -m tools.bulk_downloader.main --count 500 --output dataset/originals
```

## Usage

Run from the **project root** directory:

```bash
# Default: generate ~1,000 images
python -m tools.dataset_generator.main

# Custom source and output directories
python -m tools.dataset_generator.main --source ./my_images --output ./test_dataset

# Custom category counts
python -m tools.dataset_generator.main --duplicates 200 --blurred 100 --dark 100

# Reproducible generation with seed
python -m tools.dataset_generator.main --seed 42

# Verbose debug logging
python -m tools.dataset_generator.main -v
```

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--source` | `dataset/originals` | Source directory with original images |
| `--output` | `dataset/photomind_v1` | Output directory for the dataset |
| `--duplicates` | `100` | Exact duplicate copies |
| `--resized` | `100` | Resized + JPEG compressed images |
| `--blurred` | `75` | Gaussian blurred images |
| `--dark` | `75` | Underexposed (darkened) images |
| `--bright` | `50` | Overexposed (brightened) images |
| `--rotated` | `50` | Rotated images (cardinal + arbitrary) |
| `--cropped` | `50` | Randomly cropped images |
| `--seed` | — | Random seed for reproducibility |
| `-v` | — | Enable debug logging |

## Output Structure

```
dataset/photomind_v1/
├── originals/          # 500 source copies
│   ├── 0.jpg
│   ├── 1.jpg
│   └── ...
├── duplicates/         # 100 exact duplicates
│   ├── duplicates_0000_42.jpg
│   └── ...
├── resized/            # 100 resized + compressed
│   ├── resized_0000_15.jpg
│   └── ...
├── blurred/            # 75 Gaussian blurred
│   ├── blurred_0000_88.jpg
│   └── ...
├── dark/               # 75 underexposed
│   ├── dark_0000_7.jpg
│   └── ...
├── bright/             # 50 overexposed
│   ├── bright_0000_120.jpg
│   └── ...
├── rotated/            # 50 rotated
│   ├── rotated_0000_33.jpg
│   └── ...
├── cropped/            # 50 randomly cropped
│   ├── cropped_0000_56.jpg
│   └── ...
└── manifest.json       # Dataset manifest with file counts
```

## Transform Details

| Transform | What It Does | Parameters |
|---|---|---|
| **Exact Duplicate** | Byte-level copy of the original | — |
| **Resize + Compress** | Scale to 25–75% + JPEG quality 15–50 | Random scale, random quality |
| **Gaussian Blur** | Blur with radius 2.0–8.0 | Random radius |
| **Darken** | Brightness factor 0.15–0.45 | Simulates underexposure |
| **Brighten** | Brightness factor 1.6–2.5 | Simulates overexposure |
| **Rotate** | 90°/180°/270° or arbitrary 5°–45° | 30% chance of arbitrary |
| **Random Crop** | Crop 40–75% of original area | Random position + size |

## Architecture

```
tools/dataset_generator/
├── __init__.py         # Package marker
├── config.py           # GeneratorConfig + TransformParams dataclasses
├── transforms.py       # 7 transform functions + EXIF helpers + registry
├── generator.py        # DatasetGenerator engine + GenerationStats
├── main.py             # CLI entry point (argparse, logging, phases)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Use Cases in PhotoMind AI

This synthetic dataset is designed for testing:

- **Duplicate Detection** — Exact and near-duplicate identification
- **CLIP Embeddings** — Embedding quality across image distortions
- **Semantic Search** — Query accuracy with degraded images
- **Image Quality Analysis** — Detecting blur, exposure, and compression
- **Thumbnail Generation** — Resize/crop pipeline validation
- **Vector Search Benchmarking** — Qdrant index performance under scale

## Resuming Interrupted Generation

Re-run the same command. The generator skips all existing files:

```bash
# First run (interrupted at 400 images)
python -m tools.dataset_generator.main

# Resume — skips the 400 already generated
python -m tools.dataset_generator.main
```
