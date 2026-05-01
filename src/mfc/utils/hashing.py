"""Hashing helpers: stable, short ids derived from URLs."""

from __future__ import annotations

import hashlib

_ID_LENGTH = 16


def url_hash(url: str) -> str:
    """Short, stable hex id for a URL. Used as ``record_id``."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:_ID_LENGTH]
