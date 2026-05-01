"""Stage I/O locations.

The pipeline is resumable: each stage reads from the previous stage's output
directory and writes to its own. All paths are relative to the working
directory the CLI is invoked from (typically the repo root).
"""

from __future__ import annotations

from pathlib import Path

DATA_ROOT = Path("data")
RAW_ROOT = DATA_ROOT / "raw"
INTERIM_ROOT = DATA_ROOT / "interim"
PROCESSED_ROOT = DATA_ROOT / "processed"

HTTP_CACHE_DIR = RAW_ROOT / "http_cache"


def source_interim_dir(source_id: str) -> Path:
    return INTERIM_ROOT / source_id


def urls_path(source_id: str) -> Path:
    return source_interim_dir(source_id) / "urls.jsonl"


def fetched_path(source_id: str) -> Path:
    return source_interim_dir(source_id) / "fetched.jsonl"


def records_path(source_id: str) -> Path:
    return source_interim_dir(source_id) / "records.jsonl"


DEDUPED_PATH = INTERIM_ROOT / "all" / "records_deduped.jsonl"

LABELS_ROOT = DATA_ROOT / "labels"
MANUAL_LABELS_PATH = LABELS_ROOT / "manual_labels.parquet"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
