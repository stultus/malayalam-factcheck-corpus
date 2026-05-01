"""ClaimReview JSON-LD extractor tests."""

from __future__ import annotations

import json

from mfc.extract.claimreview import extract_claimreview


def test_factcrescendo_ml_emits_no_claimreview(
    factcrescendo_ml_pages: list[tuple[str, str]],
) -> None:
    assert factcrescendo_ml_pages, "fixtures missing"
    for stem, html in factcrescendo_ml_pages:
        result = extract_claimreview(html, f"https://example.com/{stem}")
        assert result is None, f"unexpected ClaimReview hit on {stem}"


def test_synthetic_claimreview_extracts_fields() -> None:
    payload = {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "claimReviewed": "The earth is flat",
        "datePublished": "2026-01-15",
        "name": "Fact Check: flat earth claim",
        "reviewRating": {"@type": "Rating", "alternateName": "False", "ratingValue": "1"},
    }
    html = (
        "<html><head>"
        "<link rel='canonical' href='https://example.com/x'/>"
        f"<script type='application/ld+json'>{json.dumps(payload)}</script>"
        "</head><body><article>Long debunking prose here.</article></body></html>"
    )
    result = extract_claimreview(
        html, "https://example.com/x", body_selector="article", title_selector="h1"
    )
    assert result is not None
    assert result.claim_text == "The earth is flat"
    assert result.verdict_raw == "False"
    assert result.published_date_raw == "2026-01-15"
    assert result.url_canonical == "https://example.com/x"
    assert result.evidence_text == "Long debunking prose here."
    assert result.extractor_used == "claimreview_jsonld"
    assert result.extractor_confidence == 1.0


def test_partial_claimreview_lowers_confidence() -> None:
    payload = {
        "@type": "ClaimReview",
        "claimReviewed": "x",
        "datePublished": "2026-01-15",
        "reviewRating": {"alternateName": "False"},
    }
    block = json.dumps(payload)
    html = f"<html><body><script type='application/ld+json'>{block}</script></body></html>"
    result = extract_claimreview(html, "https://example.com/y")
    assert result is not None
    assert result.extractor_confidence == 0.7


def test_claimreview_inside_graph() -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "name": "ignored"},
            {
                "@type": "ClaimReview",
                "claimReviewed": "graph claim",
                "datePublished": "2026-02-01",
                "reviewRating": {"alternateName": "Misleading"},
            },
        ],
    }
    block = json.dumps(payload)
    html = f"<html><body><script type='application/ld+json'>{block}</script></body></html>"
    result = extract_claimreview(html, "https://example.com/g")
    assert result is not None
    assert result.claim_text == "graph claim"
    assert result.verdict_raw == "Misleading"
