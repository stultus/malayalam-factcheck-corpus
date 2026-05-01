"""CSS-selector extractor tests against the Fact Crescendo Malayalam fixtures."""

from __future__ import annotations

from mfc.extract.selectors import extract_selectors

FC_SELECTORS = {
    "title": "h1.entry-title, h1.tdb-title-text, span.fc-title-text",
    "content": "div.td-post-content, article .entry-content",
    "published_date": "meta[property='article:published_time'], time.entry-date",
    "claim": "span.fc-title-text, .claim-box, .claimreview-claim",
    "verdict": "span.fc-result-text, .rating-box, .claimreview-rating",
    "author": ".fc-author-card a, .td-post-author-name a, .author-name",
}


def test_factcrescendo_selectors_extract_every_fixture(
    factcrescendo_ml_pages: list[tuple[str, str]],
) -> None:
    for stem, html in factcrescendo_ml_pages:
        result = extract_selectors(html, f"https://example.com/{stem}", FC_SELECTORS)
        assert result is not None, f"{stem}: selectors returned None"
        assert result.claim_text, f"{stem}: empty claim"
        assert result.verdict_raw, f"{stem}: empty verdict"
        assert result.extractor_used == "css_selectors"


def test_selectors_returns_none_when_claim_missing() -> None:
    html = "<html><body><div>only body</div></body></html>"
    selectors: dict[str, str | None] = {"claim": ".missing", "verdict": ".missing"}
    assert extract_selectors(html, "https://example.com/x", selectors) is None


def test_selectors_reads_meta_content_attribute() -> None:
    html = (
        "<html><head>"
        "<meta property='article:published_time' content='2026-04-20T10:00:00+05:30'/>"
        "</head><body>"
        "<span class='claim'>x</span><span class='verdict'>False</span>"
        "</body></html>"
    )
    selectors: dict[str, str | None] = {
        "claim": ".claim",
        "verdict": ".verdict",
        "published_date": "meta[property='article:published_time']",
    }
    result = extract_selectors(html, "https://example.com/m", selectors)
    assert result is not None
    assert result.published_date_raw == "2026-04-20T10:00:00+05:30"
