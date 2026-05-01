"""trafilatura readability fallback tests."""

from __future__ import annotations

from mfc.extract.readability import extract_readability


def test_readability_recovers_body_from_factcrescendo(
    factcrescendo_ml_pages: list[tuple[str, str]],
) -> None:
    hits = 0
    for stem, html in factcrescendo_ml_pages:
        result = extract_readability(html, f"https://example.com/{stem}")
        if result is None:
            continue
        hits += 1
        assert result.extractor_used == "readability"
        assert result.extractor_confidence == 0.3
        assert result.verdict_raw == ""
        assert result.evidence_text
    assert hits >= 1, "readability should rescue at least one FC fixture"


def test_readability_strips_fact_check_prefix() -> None:
    html = (
        "<html><head><title>Fact Check: synthetic claim</title></head>"
        "<body><article><p>"
        "Long enough body to satisfy trafilatura. " * 40 + "</p></article></body></html>"
    )
    result = extract_readability(html, "https://example.com/p")
    assert result is not None
    assert "Fact Check" not in result.claim_text
    assert result.claim_text.endswith("synthetic claim")


def test_readability_returns_none_on_empty_body() -> None:
    html = "<html><body></body></html>"
    assert extract_readability(html, "https://example.com/empty") is None
