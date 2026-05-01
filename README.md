# malayalam-factcheck-corpus

A batch pipeline that turns Malayalam fact-check articles from IFCN-certified Indian portals into a versioned Parquet corpus, ready for training claim-verification and misinformation-detection models.

Given `configs/malayalam_factcheck_sources.json`, the pipeline discovers article URLs, fetches them (cached, rate-limited, robots-respecting), extracts structured fields (preferring schema.org `ClaimReview` JSON-LD), normalizes verdicts and dates, dedups claims across sources, and writes `corpus_v{N}.parquet` + a `quarantine_v{N}.parquet` for records that fail validation.

## Status

All six pipeline stages are wired and a full pilot run (`mfc all --pilot`) currently produces `data/processed/corpus_v1.parquet` with 170 records across 6 of the 8 configured sources. A localhost browser-based labelling tool (`mfc label`) sits alongside the pipeline so the long tail of `verdict_canonical = "unknown"` records can be reviewed by hand.

Working:

- All stages: `mfc validate-config`, `discover`, `fetch`, `extract`, `normalize`, `dedup`, `package`, plus the `all` orchestrator.
- Three-tier discovery fallback: RSS → XML sitemap → HTML category page, with optional per-source `article_url_pattern` regex and per-source `user_agent` override (needed where sites 403 our default UA).
- Three-tier extraction fallback: ClaimReview JSON-LD → per-source CSS selectors → trafilatura readability.
- Async httpx fetcher with a hishel SQLite HTTP cache, robots.txt registry, tenacity backoff, and per-host concurrency caps.
- Verdict canonicalisation (longest-alias-wins), Malayalam/Latin/mixed script detection, `dateparser`-backed UTC dates, and semantic dedup via multilingual sentence embeddings (greedy cosine clustering, threshold 0.85).
- zstd Parquet output via polars, validated through `FactCheckRecord` on the way in. Manual labels stored in a sidecar parquet (`data/labels/manual_labels.parquet`) and joined into the corpus at packaging time, overriding the auto verdict and setting `label_source = "manual"`.
- `ruff`, `mypy --strict`, and `pytest` (42 tests against committed HTML fixtures + an in-process labelling-server fixture) all pass; CI runs them on every push.

Coverage caveats from the pilot run:

- **ClaimReview JSON-LD adoption is rare in this genre.** Across the IFCN sources we could probe, 0/15 sampled URLs emit a ClaimReview block — the Yoast/SEO graphs publishers ship don't include it. CSS selectors driven by per-source config is the load-bearing extraction path; readability is the safety net for sources whose layout we haven't templated yet.
- **`newschecker_ml` is currently out of scope.** It's a Next.js SPA that hydrates article lists from streaming RSC payloads; static-HTML discovery returns no article URLs. Needs a headless browser or a publisher API.
- **`manorama_factcheck`, `mathrubhumi_factcheck`, and `pib_factcheck` produce records but the verdict is buried in prose.** The current pipeline labels these `verdict_canonical = "unknown"` (51 of the 71 pilot records). A Malayalam-language verdict-keyword classifier is the next obvious lift.

## Sources

Eight Malayalam fact-check sources are configured in `configs/malayalam_factcheck_sources.json`. Five are IFCN-certified:

- Fact Crescendo Malayalam
- Newschecker Malayalam
- NewsMeter Malayalam Fact Check
- India Today AFWA Malayalam
- Fact Crescendo (English, Kerala-tagged, for cross-lingual pairs)

Three non-IFCN sources are included as supplementary (weakly labelled, cross-verify before training use):

- Manorama Online Fact Check
- Mathrubhumi Fact Check
- PIB Fact Check (Government of India; ideologically skewed, augmentation only)

## Setup

Requires [uv](https://github.com/astral-sh/uv) and Python 3.11+.

```bash
uv sync
```

## Usage

```bash
uv run mfc --help                                          # list stages
uv run mfc validate-config                                 # validate the seed JSON

# Full pilot across every source (50 URLs each, then dedup + package):
uv run mfc all --pilot

# Or run a single source one stage at a time:
uv run mfc discover  --source factcrescendo_ml --limit 5
uv run mfc fetch     --source factcrescendo_ml
uv run mfc extract   --source factcrescendo_ml
uv run mfc normalize --source factcrescendo_ml
uv run mfc dedup
uv run mfc package   --version 1                              # internal corpus (full prose)
uv run mfc package   --version 1 --tier publishable           # permissioned subset, evidence_text snipped

# Manual labelling (browser UI on 127.0.0.1; terminal Malayalam rendering is unusable):
uv run mfc label                                           # opens default browser
uv run mfc label stats                                     # one-line verdict breakdown
uv run mfc label export --out data/labels/snapshot.json    # dump sidecar to JSON
```

Stage outputs land under `data/interim/{source_id}/` (`urls.jsonl`,
`fetched.jsonl`, `records.jsonl`) with raw HTML cached in
`data/raw/html/{source_id}/` and the final Parquet in `data/processed/`. Each
stage is independently resumable: re-running `extract` on already-fetched URLs
is free, and the hishel cache short-circuits HTTP for unchanged pages.

Dev checks:

```bash
uv run ruff check src tests scripts
uv run ruff format src tests scripts
uv run mypy --strict src
uv run pytest
```

## Layout

```
configs/malayalam_factcheck_sources.json   # sources config (treated as the seed)
src/mfc/
  cli.py                                   # typer entrypoint
  config.py                                # SourcesFile, SourceConfig, ...
  paths.py                                 # data/ layout helpers
  discovery/  rss.py sitemap.py category.py # 3-tier URL discovery fallback
  fetch/      client.py cache.py robots.py # async httpx + hishel + robots
  extract/    claimreview.py selectors.py readability.py pipeline.py
  normalize/  labels.py script.py dates.py
  dedup/      semantic.py                  # multilingual sentence-transformer cosine clustering
  corpus/     record.py writer.py          # FactCheckRecord + Parquet writer
  label/      store.py server.py static/   # localhost manual-labelling sidecar + browser UI
  utils/      hashing.py jsonl.py
scripts/                                   # validate_sources.py, sample_pilot.py, measure_claimreview_coverage.py
tests/                                     # pytest suite + committed HTML fixtures
data/                                      # gitignored; pipeline outputs
```

## Scope

Corpus only. Model training, evaluation, labelling UI, and production APIs live in separate repos and consume the Parquet output of this one.

## Legal and ethics

Building a corpus from third-party fact-check articles has copyright, data-protection, and defamation implications. Read [LEGAL.md](LEGAL.md) before publishing anything derived from this pipeline. In short:

- Local research use is squarely inside Indian fair dealing.
- Public release of `evidence_text` (full debunking prose) requires written permission from each source publisher.
- IFCN signatories are usually receptive to research requests — ask first.
- A re-fetch-from-URL release pattern is far safer than shipping article bodies.

If you are a rights holder, publisher, or named individual and want content removed, see [TAKEDOWN.md](TAKEDOWN.md).

A draft [DATASHEET.md](DATASHEET.md) (Gebru et al., *Datasheets for Datasets*) documents motivation, composition, collection, and intended uses of the corpus. It will be filled in fully as the corpus stabilises past the pilot.

## Citation

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19940702.svg)](https://doi.org/10.5281/zenodo.19940702)

If this corpus or pipeline is useful in your work, a citation would be appreciated. GitHub renders a "Cite this repository" widget from [`CITATION.cff`](CITATION.cff); the BibTeX equivalent is:

```bibtex
@misc{bhaskaran_malayalam_factcheck_corpus_2026,
  author       = {Bhaskaran, Hrishikesh},
  title        = {malayalam-factcheck-corpus},
  year         = {2026},
  version      = {0.1.1},
  doi          = {10.5281/zenodo.19940702},
  url          = {https://doi.org/10.5281/zenodo.19940702},
  howpublished = {\url{https://github.com/stultus/malayalam-factcheck-corpus}},
  note         = {Pipeline and labelled corpus of Malayalam fact-check articles}
}
```

The DOI above is the **concept DOI** — it always resolves to the latest archived version. To cite a specific snapshot, use the version DOI listed on the [Zenodo record](https://doi.org/10.5281/zenodo.19940702) (e.g. `10.5281/zenodo.19940703` for v0.1.1).

It helps reproducibility if the `version` field reflects the corpus version you actually used (`corpus_v{N}.parquet`) rather than repo HEAD, since re-runs against newer source state produce different records.

The records here are derived from third-party fact-checks, so a citation to the original publishers alongside this one is also appreciated where it fits. The `source_id` column on every record maps to the entries in [`configs/malayalam_factcheck_sources.json`](configs/malayalam_factcheck_sources.json), and the `url` column points to the canonical article — both should be enough to attribute back to the IFCN signatory or media house that did the underlying reporting.

## License

[LICENSE](LICENSE) (MIT) covers the **pipeline code only**. Any released corpus is a separate work — see [LEGAL.md](LEGAL.md) for the recommended corpus license posture.
