"""Read/write the manual-labels sidecar parquet, keyed by ``record_id``.

Writes are atomic (temp file + ``os.replace``) so a crash mid-write
can never corrupt the parquet. The store is intentionally tiny: load
the whole file into a dict on construction, mutate in memory, flush
on every change. At the scale this corpus operates (low five figures
of records, single-user labelling), that is dramatically simpler than
incremental parquet edits and the write cost is invisible.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import polars as pl
from pydantic import BaseModel, ConfigDict

from mfc.corpus.record import VerdictCanonical
from mfc.paths import MANUAL_LABELS_PATH, ensure_dir

ManualVerdict = VerdictCanonical | Literal["needs_review"]


class ManualLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    verdict: ManualVerdict
    notes: str | None = None
    labelled_at: datetime
    labeller: str = "manual"


_SCHEMA: dict[str, type[pl.DataType]] = {
    "record_id": pl.Utf8,
    "verdict": pl.Utf8,
    "notes": pl.Utf8,
    "labelled_at": pl.Utf8,
    "labeller": pl.Utf8,
}


class LabelStore:
    """In-memory dict of ``record_id -> ManualLabel``, write-through to parquet."""

    def __init__(self, path: Path = MANUAL_LABELS_PATH) -> None:
        self._path = path
        self._labels: dict[str, ManualLabel] = {}
        if path.exists():
            self._load()

    def _load(self) -> None:
        frame = pl.read_parquet(self._path)
        for row in frame.iter_rows(named=True):
            label = ManualLabel.model_validate(
                {
                    "record_id": row["record_id"],
                    "verdict": row["verdict"],
                    "notes": row["notes"],
                    "labelled_at": datetime.fromisoformat(row["labelled_at"]),
                    "labeller": row["labeller"],
                }
            )
            self._labels[label.record_id] = label

    def get(self, record_id: str) -> ManualLabel | None:
        return self._labels.get(record_id)

    def all(self) -> dict[str, ManualLabel]:
        return dict(self._labels)

    def upsert(
        self,
        record_id: str,
        verdict: ManualVerdict,
        *,
        notes: str | None = None,
        labeller: str = "manual",
    ) -> ManualLabel:
        label = ManualLabel(
            record_id=record_id,
            verdict=verdict,
            notes=notes,
            labelled_at=datetime.now(UTC),
            labeller=labeller,
        )
        self._labels[record_id] = label
        self._flush()
        return label

    def delete(self, record_id: str) -> bool:
        if record_id not in self._labels:
            return False
        del self._labels[record_id]
        self._flush()
        return True

    def __len__(self) -> int:
        return len(self._labels)

    def __contains__(self, record_id: object) -> bool:
        return record_id in self._labels

    def _flush(self) -> None:
        ensure_dir(self._path.parent)
        rows = [
            {
                "record_id": label.record_id,
                "verdict": label.verdict,
                "notes": label.notes,
                "labelled_at": label.labelled_at.isoformat(),
                "labeller": label.labeller,
            }
            for label in self._labels.values()
        ]
        frame = pl.DataFrame(rows) if rows else pl.DataFrame(schema=_SCHEMA)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".manual_labels.", suffix=".parquet", dir=self._path.parent
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            frame.write_parquet(tmp_path, compression="zstd")
            os.replace(tmp_path, self._path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
