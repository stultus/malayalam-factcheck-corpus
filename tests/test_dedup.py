"""Semantic dedup clustering tests with a stubbed encoder.

The real model (``paraphrase-multilingual-mpnet-base-v2``) is ~500 MB and
not available in CI. We monkeypatch ``mfc.dedup.semantic._encode`` to
return synthetic embeddings so the clustering logic can be tested in
isolation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from mfc.corpus.record import FactCheckRecord
from mfc.dedup import semantic


def _record(
    record_id: str,
    claim: str,
    year: int,
    source_id: str = "test_src",
) -> FactCheckRecord:
    payload: dict[str, Any] = {
        "record_id": record_id,
        "source_id": source_id,
        "url": f"https://example.com/{record_id}",
        "url_canonical": None,
        "claim_text": claim,
        "claim_text_script": "mlym",
        "evidence_text": "evidence",
        "title": claim,
        "language": "ml",
        "verdict_raw": "False",
        "verdict_canonical": "false",
        "label_source": "ifcn",
        "published_date": datetime(year, 1, 1, tzinfo=UTC),
        "crawled_date": datetime(year, 6, 1, tzinfo=UTC),
        "extractor_used": "css_selectors",
        "extractor_confidence": 0.6,
    }
    return FactCheckRecord.model_validate(payload)


def _stub_encoder(vectors: dict[str, list[float]]) -> Any:
    def encode(texts: Sequence[str], _: str) -> NDArray[Any]:
        rows = [vectors[text] for text in texts]
        arr = np.array(rows, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return arr / norms

    return encode


def test_earliest_record_is_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semantic,
        "_encode",
        _stub_encoder(
            {
                "claim a\n\nevidence": [1.0, 0.0],
                "claim a copy\n\nevidence": [0.99, 0.01],
            }
        ),
    )
    records = [
        _record("later", "claim a copy", 2026, source_id="src_b"),
        _record("earlier", "claim a", 2024, source_id="src_a"),
    ]
    out = semantic.assign_duplicates(records, threshold=0.9)
    by_id = {r.record_id: r for r in out}
    assert by_id["earlier"].duplicate_of is None
    assert by_id["later"].duplicate_of == "earlier"


def test_within_source_duplicates_are_never_clustered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two records from the same publisher must not cluster even if their
    embeddings are identical, because templatic publisher prose makes
    in-source similarity meaningless."""
    monkeypatch.setattr(
        semantic,
        "_encode",
        _stub_encoder(
            {
                "claim a\n\nevidence": [1.0, 0.0],
                "claim a copy\n\nevidence": [1.0, 0.0],
            }
        ),
    )
    records = [
        _record("a", "claim a", 2024, source_id="same_src"),
        _record("b", "claim a copy", 2025, source_id="same_src"),
    ]
    out = semantic.assign_duplicates(records, threshold=0.9)
    assert all(r.duplicate_of is None for r in out)


def test_dissimilar_claims_form_separate_clusters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semantic,
        "_encode",
        _stub_encoder({"claim a\n\nevidence": [1.0, 0.0], "claim b\n\nevidence": [0.0, 1.0]}),
    )
    records = [_record("a", "claim a", 2024), _record("b", "claim b", 2025)]
    out = semantic.assign_duplicates(records, threshold=0.85)
    assert all(r.duplicate_of is None for r in out)


def test_threshold_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    # cosine ~ 0.8 — below the 0.85 threshold so nothing clusters
    monkeypatch.setattr(
        semantic,
        "_encode",
        _stub_encoder({"x\n\nevidence": [1.0, 0.0], "y\n\nevidence": [0.8, 0.6]}),
    )
    records = [_record("x", "x", 2024), _record("y", "y", 2025)]
    out = semantic.assign_duplicates(records, threshold=0.85)
    assert all(r.duplicate_of is None for r in out)


def test_empty_input() -> None:
    assert semantic.assign_duplicates([]) == []


def test_normalize_for_dedup_strips_publisher_boilerplate() -> None:
    assert semantic.normalize_for_dedup("Some claim about X | Fact Check") == "Some claim about X"
    assert (
        semantic.normalize_for_dedup("Old video shared in wrong context - Fact Crescendo")
        == "Old video shared in wrong context"
    )
    assert (
        semantic.normalize_for_dedup("Headline trails off… - Fact Crescendo")
        == "Headline trails off"
    )
    # idempotent
    assert semantic.normalize_for_dedup("Plain claim") == "Plain claim"
    # never returns empty (would be useless for embedding)
    assert semantic.normalize_for_dedup("| Fact Check") == "| Fact Check"


def test_normalize_for_dedup_used_before_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """The encoder must see the boilerplate-stripped claim plus the evidence prefix,
    not the raw claim alone."""
    seen: list[str] = []

    def capturing_encode(texts: Sequence[str], _: str) -> NDArray[Any]:
        seen.extend(texts)
        return np.eye(len(texts), 2, dtype=np.float32)

    monkeypatch.setattr(semantic, "_encode", capturing_encode)
    records = [
        _record("a", "Claim about X | Fact Check", 2024),
        _record("b", "Different claim - Fact Crescendo", 2025),
    ]
    semantic.assign_duplicates(records)
    # Boilerplate stripped from the claim, and the stub _record sets
    # evidence_text="evidence" which gets appended.
    assert seen == ["Claim about X\n\nevidence", "Different claim\n\nevidence"]
