"""Cosine clustering on sentence-transformer embeddings.

The model (`paraphrase-multilingual-mpnet-base-v2`) is lazy-imported so
the rest of the CLI stays fast for users who never invoke `dedup`. Records
are sorted by `published_date` ascending; the earliest record in each
cluster keeps `duplicate_of=None`, every later record points back to it.

Dedup is **cross-source only**: a record can never be marked as a
duplicate of another from the same publisher. The use case is "same
viral claim debunked by three portals collapses to one cluster"; a
single publisher fact-checking the same claim twice in quick succession
is vanishingly rare. Allowing within-source clustering surfaced large
numbers of false positives on Manorama and Mathrubhumi, where the
templatic headline prose ("X said Y — Fake | Fact Check") is similar
enough to clear the threshold even when the actual claims differ.

Before embedding, ``claim_text`` is stripped of publisher boilerplate
(`| Fact Check`, `- Fact Crescendo`, trailing ellipsis, etc.) and the
first ~400 characters of ``evidence_text`` are appended for additional
content signal. Both transforms are applied only to the embedding input;
the stored ``claim_text`` and ``evidence_text`` on the record are
untouched.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from mfc.corpus.record import FactCheckRecord

if TYPE_CHECKING:
    from numpy.typing import NDArray

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
# 0.95 is conservative on purpose. The multilingual MPNet model treats
# Malayalam fact-check prose as broadly similar (templatic intros, shared
# vocabulary like വ്യാജം / പ്രചാരണം), so anything below ~0.95 produces
# more false positives than true cross-source duplicates on this genre.
# Revisit if/when the corpus grows large enough that real cross-source
# matches start appearing.
DEFAULT_THRESHOLD = 0.95
EVIDENCE_PREFIX_CHARS = 400

# Char class accepts pipe, middle dot, en-dash, em-dash, hyphen-minus.
_SEP = r"[|\u00b7\u2013\u2014\-]"
_BOILERPLATE_PATTERNS = [
    re.compile(rf"\s*{_SEP}\s*Fact\s*Check\s*$", re.IGNORECASE),
    re.compile(rf"\s*{_SEP}\s*Fact\s*Crescendo\s*$", re.IGNORECASE),
    re.compile(rf"\s*{_SEP}\s*Newsmeter\s*$", re.IGNORECASE),
    re.compile(rf"\s*{_SEP}\s*India\s*Today\s*$", re.IGNORECASE),
    re.compile(r"[\u2026.]+\s*$"),  # trailing ellipsis or "..."
]


def normalize_for_dedup(text: str) -> str:
    """Strip publisher boilerplate from a claim before similarity comparison."""
    cleaned = text
    for _ in range(3):  # patterns can chain (e.g. "… - Fact Crescendo")
        before = cleaned
        for pat in _BOILERPLATE_PATTERNS:
            cleaned = pat.sub("", cleaned)
        cleaned = cleaned.strip()
        if cleaned == before:
            break
    return cleaned or text  # never return empty; fall back to original


def _embedding_input(record: FactCheckRecord) -> str:
    claim = normalize_for_dedup(record.claim_text)
    evidence = (record.evidence_text or "")[:EVIDENCE_PREFIX_CHARS].strip()
    return f"{claim}\n\n{evidence}" if evidence else claim


def assign_duplicates(
    records: Sequence[FactCheckRecord],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    model_name: str = DEFAULT_MODEL,
) -> list[FactCheckRecord]:
    """Return records with `duplicate_of` populated; earliest per cluster keeps None."""
    if not records:
        return []

    ordered = sorted(records, key=lambda r: r.published_date)
    embeddings = _encode([_embedding_input(r) for r in ordered], model_name)

    rep_indices: list[int] = []
    duplicate_of: list[str | None] = [None] * len(ordered)

    for i, emb in enumerate(embeddings):
        best_rep = -1
        best_sim = -1.0
        for rep_i in rep_indices:
            # Cross-source only: never collapse two records from the same
            # publisher. Same-publisher dups are too rare to chase and
            # produce far too many false positives on Manorama / Mathrubhumi.
            if ordered[rep_i].source_id == ordered[i].source_id:
                continue
            sim = float(_dot(emb, embeddings[rep_i]))
            if sim >= threshold and sim > best_sim:
                best_sim = sim
                best_rep = rep_i
        if best_rep >= 0:
            duplicate_of[i] = ordered[best_rep].record_id
        else:
            rep_indices.append(i)

    return [
        record.model_copy(update={"duplicate_of": dup})
        for record, dup in zip(ordered, duplicate_of, strict=True)
    ]


def _encode(texts: list[str], model_name: str) -> NDArray[Any]:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    encoded: NDArray[Any] = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return encoded


def _dot(a: NDArray[Any], b: NDArray[Any]) -> float:
    import numpy as np

    return float(np.dot(a, b))
