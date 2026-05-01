"""Publishable subset preparation.

The internal corpus contains every field for every record. The publishable
subset is what we ship to third parties:

- Records from sources whose ``permission_status`` is not ``granted`` are
  dropped entirely. Those sources may still appear in the internal corpus
  but cannot be redistributed until publisher permission lands.
- ``evidence_text`` is the highest-risk field (full debunking prose).
  For publishable output it is replaced with a short snippet plus an
  instruction to re-fetch the original from ``url``. Short snippets fall
  inside fair-dealing/fair-use carve-outs across the jurisdictions we
  care about; full bodies do not.
- The full-prose form of any source can be unlocked once the publisher
  grants permission and that flips ``permission_status`` to ``granted``
  in ``configs/malayalam_factcheck_sources.json``.

See ``LEGAL.md`` for the field-by-field redistribution risk table that
this module operationalises.
"""

from __future__ import annotations

from dataclasses import dataclass

from mfc.config import SourcesFile
from mfc.corpus.record import FactCheckRecord

DEFAULT_SNIPPET_CHARS = 280
TRUNCATION_HINT = "[...truncated for public release; re-fetch the full article from `url`]"


@dataclass
class PublishSummary:
    kept: int
    dropped_no_permission: int
    redacted_evidence: int
    by_source: dict[str, int]
    """Per-source kept count. Sources missing from this dict were dropped wholesale."""


def prepare_publishable(
    records: list[FactCheckRecord],
    config: SourcesFile,
    *,
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
) -> tuple[list[FactCheckRecord], PublishSummary]:
    """Return ``(redacted_records, summary)`` ready to write to the publishable parquet."""
    granted = {src.id for src in config.sources if src.permission_status == "granted"}

    kept: list[FactCheckRecord] = []
    dropped = 0
    redacted = 0
    by_source: dict[str, int] = {}

    for record in records:
        if record.source_id not in granted:
            dropped += 1
            continue
        new_evidence, was_redacted = _redact(record.evidence_text, snippet_chars)
        if was_redacted:
            redacted += 1
            kept.append(record.model_copy(update={"evidence_text": new_evidence}))
        else:
            kept.append(record)
        by_source[record.source_id] = by_source.get(record.source_id, 0) + 1

    return kept, PublishSummary(
        kept=len(kept),
        dropped_no_permission=dropped,
        redacted_evidence=redacted,
        by_source=by_source,
    )


def _redact(evidence: str, snippet_chars: int) -> tuple[str, bool]:
    if len(evidence) <= snippet_chars:
        return evidence, False
    snippet = evidence[:snippet_chars].rstrip()
    return f"{snippet}… {TRUNCATION_HINT}", True
