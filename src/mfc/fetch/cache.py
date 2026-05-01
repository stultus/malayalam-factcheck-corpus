"""On-disk HTTP response cache.

Implemented as a ``hishel`` SQLite storage backed by the local filesystem
under ``data/raw/``. Hishel honours HTTP cache semantics (``If-Modified-Since``,
``ETag``, ``Cache-Control``) and stores responses as raw byte blobs in
SQLite, so a cache file cannot trigger code execution on read (no pickle).
"""

from __future__ import annotations

from pathlib import Path

import hishel

from mfc.paths import HTTP_CACHE_DIR, ensure_dir


def build_storage(cache_dir: Path | None = None) -> hishel.AsyncSqliteStorage:
    """Async SQLite-backed storage rooted at ``cache_dir``."""
    target = ensure_dir(cache_dir or HTTP_CACHE_DIR)
    return hishel.AsyncSqliteStorage(database_path=target / "http_cache.sqlite")
