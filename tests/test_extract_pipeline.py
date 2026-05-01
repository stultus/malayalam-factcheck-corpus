"""Per-source extraction smoke tests against committed HTML fixtures.

Each source has 5 fixtures committed under ``tests/fixtures/html/{source_id}/``,
captured from a real crawl of that publisher. The tests run the full
extraction pipeline (`run_extractors`) using each source's actual config from
the seed JSON, so they fail loudly when a publisher changes their markup
in a way that breaks the configured selectors or readability fallback.

CI never hits the live network: vcrpy isn't used because the fetcher writes
raw HTML to ``data/raw/html/`` already, and these fixtures are slices of
that cache. When a source's HTML structure changes, refresh by re-running
the relevant ``mfc fetch`` and copying 5 fresh files into the fixture dir.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mfc.config import SourceConfig, SourcesFile
from mfc.extract.pipeline import run_extractors

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "malayalam_factcheck_sources.json"
HTML_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"


def _source(source_id: str) -> SourceConfig:
    return SourcesFile.load(CONFIG_PATH).source(source_id)


def _load_html_fixtures(source_id: str) -> list[tuple[str, str]]:
    src_dir = HTML_FIXTURES_DIR / source_id
    return [(p.stem, p.read_text(encoding="utf-8")) for p in sorted(src_dir.glob("*.html"))]


@pytest.mark.parametrize(
    "source_id",
    [
        "factcrescendo_ml",
        "factcrescendo_en_malayalam_tag",
        "indiatoday_ml_afwa",
        "manorama_factcheck",
        "mathrubhumi_factcheck",
        "newsmeter_ml",
    ],
)
def test_extraction_returns_a_result_for_every_fixture(source_id: str) -> None:
    src = _source(source_id)
    pages = _load_html_fixtures(source_id)
    assert pages, f"no fixtures committed for {source_id}"
    for stem, html in pages:
        result = run_extractors(html, f"https://example.com/{stem}", src)
        assert result is not None, f"{source_id}/{stem}: extraction returned None"
        assert result.title, f"{source_id}/{stem}: empty title"
        assert result.evidence_text, f"{source_id}/{stem}: empty evidence_text"
        assert result.extractor_used in {
            "claimreview_jsonld",
            "css_selectors",
            "readability",
        }


def test_factcrescendo_ml_extracts_via_selectors_not_readability() -> None:
    """FC Malayalam exposes claim/verdict in dedicated CSS, so we must not
    silently fall through to readability for these fixtures."""
    src = _source("factcrescendo_ml")
    for stem, html in _load_html_fixtures("factcrescendo_ml"):
        result = run_extractors(html, f"https://example.com/{stem}", src)
        assert result is not None
        assert result.extractor_used == "css_selectors", (
            f"{stem}: regressed to {result.extractor_used} — "
            f"selector block in seed JSON likely needs updating"
        )
        assert result.claim_text
        assert result.verdict_raw
