"""LabelStore round-trip and atomic-write tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from mfc.corpus.record import FactCheckRecord
from mfc.label.store import LabelStore, ManualLabel, apply_labels


def _record(record_id: str, verdict: str = "unknown") -> FactCheckRecord:
    return FactCheckRecord(
        record_id=record_id,
        source_id="src",
        url="https://example.com/" + record_id,  # type: ignore[arg-type]
        claim_text="claim",
        claim_text_script="mlym",
        evidence_text="evidence",
        title="title",
        language="ml",
        verdict_raw="raw",
        verdict_canonical=verdict,  # type: ignore[arg-type]
        label_source="ifcn",
        published_date=datetime(2026, 1, 1, tzinfo=UTC),
        crawled_date=datetime(2026, 1, 1, tzinfo=UTC),
        extractor_used="readability",
        extractor_confidence=0.5,
    )


def _label(record_id: str, verdict: str) -> ManualLabel:
    return ManualLabel(
        record_id=record_id,
        verdict=verdict,  # type: ignore[arg-type]
        labelled_at=datetime(2026, 5, 1, tzinfo=UTC),
    )


def test_upsert_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "manual_labels.parquet"
    store = LabelStore(path)
    store.upsert("rec_1", "false", notes="clear fabrication")
    store.upsert("rec_2", "needs_review")

    reopened = LabelStore(path)
    assert len(reopened) == 2
    assert reopened.get("rec_1") is not None
    label = reopened.get("rec_1")
    assert label is not None
    assert label.verdict == "false"
    assert label.notes == "clear fabrication"

    other = reopened.get("rec_2")
    assert other is not None
    assert other.verdict == "needs_review"
    assert other.notes is None


def test_upsert_overwrites_in_place(tmp_path: Path) -> None:
    path = tmp_path / "manual_labels.parquet"
    store = LabelStore(path)
    store.upsert("rec_1", "false")
    store.upsert("rec_1", "misleading", notes="updated")

    assert len(store) == 1
    label = store.get("rec_1")
    assert label is not None
    assert label.verdict == "misleading"
    assert label.notes == "updated"


def test_delete_returns_false_when_missing(tmp_path: Path) -> None:
    store = LabelStore(tmp_path / "manual_labels.parquet")
    assert store.delete("nonexistent") is False
    store.upsert("rec_1", "false")
    assert store.delete("rec_1") is True
    assert "rec_1" not in store


def test_invalid_verdict_rejected(tmp_path: Path) -> None:
    store = LabelStore(tmp_path / "manual_labels.parquet")
    with pytest.raises(ValidationError):
        store.upsert("rec_1", "bogus")  # type: ignore[arg-type]


def test_empty_store_writes_schema_only_parquet(tmp_path: Path) -> None:
    path = tmp_path / "manual_labels.parquet"
    store = LabelStore(path)
    store.upsert("rec_1", "false")
    store.delete("rec_1")
    # The flush after delete leaves an empty parquet that must still be readable.
    reopened = LabelStore(path)
    assert len(reopened) == 0


def test_no_temp_files_left_behind(tmp_path: Path) -> None:
    path = tmp_path / "manual_labels.parquet"
    store = LabelStore(path)
    store.upsert("rec_1", "false")
    store.upsert("rec_2", "true")
    leftover = list(tmp_path.glob(".manual_labels.*"))
    assert leftover == []


def test_not_fact_check_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "manual_labels.parquet"
    store = LabelStore(path)
    store.upsert("rec_x", "not_fact_check", notes="generic news article tagged in the FC section")

    reopened = LabelStore(path)
    label = reopened.get("rec_x")
    assert label is not None
    assert label.verdict == "not_fact_check"
    assert label.notes == "generic news article tagged in the FC section"


def test_apply_labels_overrides_canonical_verdicts() -> None:
    records = [_record("a"), _record("b")]
    labels = {"a": _label("a", "false")}
    merged, summary = apply_labels(records, labels)
    by_id = {r.record_id: r for r in merged}
    assert summary.overridden == 1
    assert summary.rejected == 0
    assert by_id["a"].verdict_canonical == "false"
    assert by_id["a"].label_source == "manual"
    assert by_id["b"].verdict_canonical == "unknown"
    assert by_id["b"].label_source == "ifcn"


def test_apply_labels_drops_not_fact_check() -> None:
    records = [_record("a"), _record("b"), _record("c")]
    labels = {"b": _label("b", "not_fact_check")}
    merged, summary = apply_labels(records, labels)
    assert [r.record_id for r in merged] == ["a", "c"]
    assert summary.rejected == 1
    assert summary.overridden == 0


def test_apply_labels_preserves_auto_verdict_for_needs_review() -> None:
    records = [_record("a", verdict="false")]
    labels = {"a": _label("a", "needs_review")}
    merged, summary = apply_labels(records, labels)
    assert len(merged) == 1
    assert merged[0].verdict_canonical == "false"
    assert merged[0].label_source == "ifcn"
    assert summary.overridden == 0
    assert summary.rejected == 0
