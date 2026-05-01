"""Validate records and write Parquet with zstd compression via polars.

Records are passed through :class:`FactCheckRecord` validation before
serialization. Anything that fails validation is the caller's problem to
quarantine; this writer never silently drops rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import polars as pl

from mfc.corpus.record import FactCheckRecord
from mfc.paths import ensure_dir


def write_parquet(records: Iterable[FactCheckRecord], path: Path) -> int:
    """Write ``records`` to ``path`` as Parquet with zstd compression. Returns row count."""
    rows: list[dict[str, Any]] = [_to_row(r) for r in records]
    ensure_dir(path.parent)
    frame = pl.DataFrame(rows) if rows else pl.DataFrame(schema=_empty_schema())
    frame.write_parquet(path, compression="zstd")
    return frame.height


def _to_row(record: FactCheckRecord) -> dict[str, Any]:
    data = record.model_dump(mode="json")
    data["url"] = str(record.url)
    if record.url_canonical is not None:
        data["url_canonical"] = str(record.url_canonical)
    return data


def _empty_schema() -> dict[str, type[pl.DataType]]:
    return {
        "record_id": pl.Utf8,
        "source_id": pl.Utf8,
        "url": pl.Utf8,
        "url_canonical": pl.Utf8,
        "claim_text": pl.Utf8,
        "claim_text_script": pl.Utf8,
        "evidence_text": pl.Utf8,
        "title": pl.Utf8,
        "language": pl.Utf8,
        "verdict_raw": pl.Utf8,
        "verdict_canonical": pl.Utf8,
        "label_source": pl.Utf8,
        "published_date": pl.Utf8,
        "crawled_date": pl.Utf8,
        "extractor_used": pl.Utf8,
        "extractor_confidence": pl.Float64,
        "claim_embedding_hash": pl.Utf8,
        "duplicate_of": pl.Utf8,
    }
