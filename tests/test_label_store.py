"""LabelStore round-trip and atomic-write tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from mfc.label.store import LabelStore


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
