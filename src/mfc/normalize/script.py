"""Detect Malayalam vs Latin vs mixed (Manglish) script in claim text.

Counts Malayalam Unicode block (``U+0D00``-``U+0D7F``) and basic Latin
letter codepoints, ignoring whitespace, digits, and punctuation. The
script tag is ``mlym`` if ≥80% of letter codepoints fall in the
Malayalam block, ``latn`` if ≥80% are Latin, otherwise ``mixed``. The
corpus preserves the original script: transliteration is left to
downstream model preprocessing.
"""

from __future__ import annotations

from mfc.corpus.record import ClaimScript

_MLYM_START = 0x0D00
_MLYM_END = 0x0D7F
_THRESHOLD = 0.8


def detect_script(text: str) -> ClaimScript:
    mlym = 0
    latn = 0
    for ch in text:
        if not ch.isalpha():
            continue
        code = ord(ch)
        if _MLYM_START <= code <= _MLYM_END:
            mlym += 1
        elif ch.isascii():
            latn += 1

    total = mlym + latn
    if total == 0:
        return "unknown"
    if mlym / total >= _THRESHOLD:
        return "mlym"
    if latn / total >= _THRESHOLD:
        return "latn"
    return "mixed"
