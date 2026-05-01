"""Tests for the publishable-subset preparation logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mfc.config import SourcesFile
from mfc.corpus.publish import (
    DEFAULT_SNIPPET_CHARS,
    TRUNCATION_HINT,
    prepare_publishable,
)
from mfc.corpus.record import FactCheckRecord


def _make_record(record_id: str, source_id: str, evidence: str = "short body") -> FactCheckRecord:
    return FactCheckRecord.model_validate(
        {
            "record_id": record_id,
            "source_id": source_id,
            "url": f"https://example.test/{record_id}",
            "claim_text": "claim",
            "claim_text_script": "mlym",
            "evidence_text": evidence,
            "title": "title",
            "language": "ml",
            "verdict_raw": "False",
            "verdict_canonical": "false",
            "label_source": "ifcn",
            "published_date": datetime(2026, 1, 1, tzinfo=UTC),
            "crawled_date": datetime(2026, 5, 1, tzinfo=UTC),
            "extractor_used": "css_selectors",
            "extractor_confidence": 0.6,
        }
    )


def _make_config(perms: dict[str, str]) -> SourcesFile:
    sources: list[dict[str, Any]] = []
    for src_id, status in perms.items():
        sources.append(
            {
                "id": src_id,
                "name": src_id,
                "base_url": f"https://example.test/{src_id}",
                "language": "ml",
                "ifcn_signatory": True,
                "permission_status": status,
                "discovery": {"rss": f"https://example.test/{src_id}/feed"},
                "extraction": {"claimreview_jsonld": True},
            }
        )
    payload = {
        "schema_version": "1.0",
        "description": "test",
        "canonical_labels": {},
        "extraction_priority": ["claimreview_jsonld"],
        "global_crawler_policy": {
            "user_agent": "test",
            "default_delay_seconds": 1,
            "max_concurrent_per_host": 1,
            "timeout_seconds": 10,
            "retry_attempts": 1,
        },
        "sources": sources,
    }
    return SourcesFile.model_validate(payload)


def test_drops_records_without_permission() -> None:
    config = _make_config({"src_a": "granted", "src_b": "unasked", "src_c": "denied"})
    records = [
        _make_record("rec_1", "src_a"),
        _make_record("rec_2", "src_b"),
        _make_record("rec_3", "src_c"),
        _make_record("rec_4", "src_a"),
    ]
    kept, summary = prepare_publishable(records, config)
    assert summary.kept == 2
    assert summary.dropped_no_permission == 2
    assert {r.source_id for r in kept} == {"src_a"}
    assert summary.by_source == {"src_a": 2}


def test_short_evidence_left_untouched() -> None:
    config = _make_config({"src_a": "granted"})
    record = _make_record("rec_1", "src_a", evidence="brief")
    kept, summary = prepare_publishable(records=[record], config=config)
    assert summary.redacted_evidence == 0
    assert kept[0].evidence_text == "brief"


def test_long_evidence_truncated_with_hint() -> None:
    config = _make_config({"src_a": "granted"})
    long_text = "x" * 2000
    record = _make_record("rec_1", "src_a", evidence=long_text)
    kept, summary = prepare_publishable(records=[record], config=config, snippet_chars=100)
    assert summary.redacted_evidence == 1
    assert kept[0].evidence_text.startswith("x" * 100)
    assert TRUNCATION_HINT in kept[0].evidence_text
    assert len(kept[0].evidence_text) < len(long_text)


def test_default_snippet_length_is_280() -> None:
    config = _make_config({"src_a": "granted"})
    long_text = "y" * (DEFAULT_SNIPPET_CHARS + 50)
    record = _make_record("rec_1", "src_a", evidence=long_text)
    kept, _ = prepare_publishable(records=[record], config=config)
    assert kept[0].evidence_text.startswith("y" * DEFAULT_SNIPPET_CHARS)


def test_empty_when_no_source_granted() -> None:
    config = _make_config({"src_a": "unasked", "src_b": "requested"})
    records = [_make_record("rec_1", "src_a"), _make_record("rec_2", "src_b")]
    kept, summary = prepare_publishable(records, config)
    assert kept == []
    assert summary.kept == 0
    assert summary.dropped_no_permission == 2
    assert summary.by_source == {}
