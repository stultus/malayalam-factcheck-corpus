"""Rebuild a full corpus from a published labels-overlay parquet.

The publishable parquet drops or truncates ``evidence_text`` because the
publisher's debunking prose is the most copyright-sensitive field. A
consumer of the released corpus can re-fetch each article from its
``url`` and reconstruct the full record locally — that is the safe
distribution pattern: we share verdicts and URLs, the consumer
materialises the prose on their own machine.

This module owns the rehydration loop. It reuses the same fetch +
extract + normalize plumbing the build pipeline uses, so a rehydrated
record is structurally identical to one produced by ``mfc all`` against
the live source. The verdict and ``label_source`` come from the input
parquet (those are the labels we shipped); everything else is re-derived
from the freshly-fetched HTML so consumers always have current
extractions even if a publisher edits an article.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from loguru import logger

from mfc.config import SourceConfig, SourcesFile
from mfc.corpus.record import FactCheckRecord
from mfc.corpus.writer import write_parquet
from mfc.extract.pipeline import run_extractors
from mfc.fetch.client import RobotsDisallowed, open_fetch_client
from mfc.normalize.dates import parse_date
from mfc.normalize.script import detect_script


@dataclass
class RehydrateSummary:
    requested: int = 0
    rehydrated: int = 0
    skipped_unknown_source: int = 0
    skipped_fetch_failed: int = 0
    skipped_extract_failed: int = 0
    skipped_unparseable_date: int = 0
    by_source: dict[str, int] = field(default_factory=dict)


REQUIRED_INPUT_COLUMNS = (
    "record_id",
    "source_id",
    "url",
    "verdict_canonical",
    "label_source",
)


def _read_label_rows(path: Path) -> list[dict[str, Any]]:
    frame = pl.read_parquet(path)
    missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"input parquet {path} is missing required columns: {missing}. "
            "Expected a publishable-tier corpus (or compatible labels overlay)."
        )
    rows: list[dict[str, Any]] = []
    for row in frame.iter_rows(named=True):
        rows.append(dict(row))
    return rows


def rehydrate_one(
    *,
    html: str,
    label_row: dict[str, Any],
    source: SourceConfig,
    fetched_at: datetime | None = None,
) -> FactCheckRecord | None:
    """Build a :class:`FactCheckRecord` from fresh HTML + the input label row.

    Returns ``None`` if extraction or date parsing fails. Verdict and
    ``label_source`` come from ``label_row`` (those are the published
    labels we are re-attaching); every other field is re-derived from
    the extractor output so the rehydrated record reflects the *current*
    state of the article.
    """
    url = str(label_row["url"])
    result = run_extractors(html, url, source)
    if result is None:
        return None
    published = parse_date(result.published_date_raw)
    if published is None:
        return None
    crawled = fetched_at or datetime.now(UTC)
    payload = {
        "record_id": label_row["record_id"],
        "source_id": source.id,
        "url": url,
        "url_canonical": result.url_canonical,
        "claim_text": result.claim_text,
        "claim_text_script": detect_script(result.claim_text),
        "evidence_text": result.evidence_text,
        "title": result.title,
        "language": source.language,
        "verdict_raw": result.verdict_raw,
        "verdict_canonical": label_row["verdict_canonical"],
        "label_source": label_row["label_source"],
        "published_date": published,
        "crawled_date": crawled,
        "extractor_used": result.extractor_used,
        "extractor_confidence": result.extractor_confidence,
        "claim_embedding_hash": label_row.get("claim_embedding_hash"),
        "duplicate_of": label_row.get("duplicate_of"),
    }
    return FactCheckRecord.model_validate(payload)


async def rehydrate_corpus(
    input_path: Path,
    output_path: Path,
    config: SourcesFile,
) -> RehydrateSummary:
    """Re-fetch every URL in ``input_path`` and write a full corpus to ``output_path``."""
    label_rows = _read_label_rows(input_path)
    summary = RehydrateSummary(requested=len(label_rows))
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in label_rows:
        by_source.setdefault(row["source_id"], []).append(row)

    out_records: list[FactCheckRecord] = []

    async with open_fetch_client(config.global_crawler_policy) as client:
        for source_id, rows in by_source.items():
            try:
                src = config.source(source_id)
            except KeyError:
                summary.skipped_unknown_source += len(rows)
                logger.warning(
                    "rehydrate: source not in config; skipping",
                    source_id=source_id,
                    count=len(rows),
                )
                continue
            headers = {"User-Agent": src.user_agent} if src.user_agent else None
            for row in rows:
                url = str(row["url"])
                try:
                    response = await client.get(url, headers=headers)
                except RobotsDisallowed:
                    summary.skipped_fetch_failed += 1
                    logger.warning("rehydrate: robots disallowed", source_id=src.id, url=url)
                    continue
                except Exception as err:
                    summary.skipped_fetch_failed += 1
                    logger.warning(
                        "rehydrate: fetch failed",
                        source_id=src.id,
                        url=url,
                        error=str(err),
                    )
                    continue
                record = rehydrate_one(html=response.text, label_row=row, source=src)
                if record is None:
                    if run_extractors(response.text, url, src) is None:
                        summary.skipped_extract_failed += 1
                    else:
                        summary.skipped_unparseable_date += 1
                    continue
                out_records.append(record)
                summary.rehydrated += 1
                summary.by_source[src.id] = summary.by_source.get(src.id, 0) + 1

    _write(out_records, output_path)
    return summary


def _write(records: Iterable[FactCheckRecord], path: Path) -> None:
    write_parquet(list(records), path)
