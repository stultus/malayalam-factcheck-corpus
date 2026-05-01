"""Tests for the consumer-side rehydration logic.

The async ``rehydrate_corpus`` is mostly orchestration around the sync
``rehydrate_one`` core; we exercise the core directly against the
committed Fact Crescendo HTML fixtures so we don't have to mock the
HTTP client to cover the data-shape correctness.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from mfc.config import SourceConfig
from mfc.rehydrate import (
    REQUIRED_INPUT_COLUMNS,
    _read_label_rows,
    rehydrate_one,
)

FC_SELECTORS: dict[str, str | None] = {
    "title": "h1.entry-title, h1.tdb-title-text, span.fc-title-text",
    "content": "div.td-post-content, article .entry-content",
    "published_date": "meta[property='article:published_time'], time.entry-date",
    "claim": "span.fc-title-text, .claim-box, .claimreview-claim",
    "verdict": "span.fc-result-text, .rating-box, .claimreview-rating",
    "author": ".fc-author-card a, .td-post-author-name a, .author-name",
}


def _fc_source() -> SourceConfig:
    return SourceConfig.model_validate(
        {
            "id": "factcrescendo_ml",
            "name": "Fact Crescendo Malayalam",
            "base_url": "https://malayalam.factcrescendo.com",
            "language": "ml",
            "ifcn_signatory": True,
            "permission_status": "unasked",
            "discovery": {"rss": "https://malayalam.factcrescendo.com/feed/"},
            "extraction": {"claimreview_jsonld": True, "selectors": FC_SELECTORS},
        }
    )


def test_rehydrate_one_keeps_published_verdict_replaces_evidence(
    factcrescendo_ml_pages: list[tuple[str, str]],
) -> None:
    src = _fc_source()
    stem, html = factcrescendo_ml_pages[0]
    label_row: dict[str, Any] = {
        "record_id": stem,
        "source_id": src.id,
        "url": f"https://malayalam.factcrescendo.com/{stem}",
        "verdict_canonical": "false",
        "label_source": "manual",
    }
    record = rehydrate_one(html=html, label_row=label_row, source=src)
    assert record is not None
    # Published label survives the re-fetch (this is the whole point — we ship
    # the label, the consumer re-derives everything else).
    assert record.verdict_canonical == "false"
    assert record.label_source == "manual"
    # Evidence was re-derived from HTML, not blank.
    assert record.evidence_text
    assert record.title
    assert record.claim_text
    # Identity preserved.
    assert record.record_id == stem
    assert record.source_id == src.id


def test_rehydrate_one_returns_none_when_html_unparseable() -> None:
    src = _fc_source()
    label_row: dict[str, Any] = {
        "record_id": "rec_x",
        "source_id": src.id,
        "url": "https://malayalam.factcrescendo.com/none",
        "verdict_canonical": "false",
        "label_source": "ifcn",
    }
    record = rehydrate_one(
        html="<html><body>nothing structured here</body></html>",
        label_row=label_row,
        source=src,
    )
    assert record is None


def test_read_label_rows_rejects_missing_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.parquet"
    pl.DataFrame({"url": ["x"], "record_id": ["y"]}).write_parquet(bad)
    with pytest.raises(ValueError, match="missing required columns"):
        _read_label_rows(bad)


def test_read_label_rows_returns_dicts(tmp_path: Path) -> None:
    good = tmp_path / "good.parquet"
    rows = [{col: f"v_{col}_{i}" for col in REQUIRED_INPUT_COLUMNS} for i in range(3)]
    pl.DataFrame(rows).write_parquet(good)
    out = _read_label_rows(good)
    assert len(out) == 3
    for row in out:
        for col in REQUIRED_INPUT_COLUMNS:
            assert col in row


def test_rehydrate_one_uses_supplied_fetched_at(
    factcrescendo_ml_pages: list[tuple[str, str]],
) -> None:
    src = _fc_source()
    stem, html = factcrescendo_ml_pages[0]
    label_row: dict[str, Any] = {
        "record_id": stem,
        "source_id": src.id,
        "url": f"https://malayalam.factcrescendo.com/{stem}",
        "verdict_canonical": "misleading",
        "label_source": "manual",
    }
    fetched = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    record = rehydrate_one(html=html, label_row=label_row, source=src, fetched_at=fetched)
    assert record is not None
    assert record.crawled_date == fetched
