"""Cosine clustering on sentence-transformer embeddings.

The model (`paraphrase-multilingual-mpnet-base-v2`) is lazy-imported so
the rest of the CLI stays fast for users who never invoke `dedup`. Records
are sorted by `published_date` ascending; the earliest record in each
cluster keeps `duplicate_of=None`, every later record points back to it.
The cosine threshold defaults to 0.85 per CLAUDE.md design rule 5.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from mfc.corpus.record import FactCheckRecord

if TYPE_CHECKING:
    from numpy.typing import NDArray

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_THRESHOLD = 0.85


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
    embeddings = _encode([r.claim_text for r in ordered], model_name)

    rep_indices: list[int] = []
    duplicate_of: list[str | None] = [None] * len(ordered)

    for i, emb in enumerate(embeddings):
        best_rep = -1
        best_sim = -1.0
        for rep_i in rep_indices:
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
