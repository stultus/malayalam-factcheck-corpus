# malayalam-factcheck-corpus

A batch pipeline that turns Malayalam fact-check articles from IFCN-certified Indian portals into a versioned Parquet corpus, ready for training claim-verification and misinformation-detection models.

Given `configs/malayalam_factcheck_sources.json`, the pipeline discovers article URLs, fetches them (cached, rate-limited, robots-respecting), extracts structured fields (preferring schema.org `ClaimReview` JSON-LD), normalizes verdicts and dates, dedups claims across sources, and writes `corpus_v{N}.parquet` + a `quarantine_v{N}.parquet` for records that fail validation.

## Status

Vertical slice is live end-to-end on `factcrescendo_ml`. A 5-URL pilot run goes
discover → fetch → extract → normalize → package and writes a valid
`data/processed/corpus_v1.parquet`.

Working:

- `mfc validate-config`, `discover`, `fetch`, `extract`, `normalize`, `package` are wired.
- ClaimReview JSON-LD is the primary extractor; per-source CSS selectors are the fallback.
- Async httpx fetcher with a hishel SQLite HTTP cache, robots.txt registry, tenacity backoff, and per-host concurrency caps.
- Verdict canonicalisation (longest-alias-wins), Malayalam/Latin/mixed script detection, and `dateparser`-backed UTC date parsing.
- zstd Parquet output via polars, validated through `FactCheckRecord` on the way in.
- `ruff`, `ruff format`, and `mypy --strict` pass; CI runs them on every push.

Not yet implemented: `dedup` (semantic clustering), `all` orchestration, the
trafilatura readability fallback, and vcrpy cassettes for offline CI testing.

Pilot finding: `factcrescendo_ml` currently emits **no** ClaimReview JSON-LD,
so all 5 records came from the selectors fallback at `extractor_confidence = 0.6`.
Coverage on the other four IFCN sources has not been measured yet.

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

# Single-source pilot, end-to-end:
uv run mfc discover  --source factcrescendo_ml --limit 5
uv run mfc fetch     --source factcrescendo_ml
uv run mfc extract   --source factcrescendo_ml
uv run mfc normalize --source factcrescendo_ml
uv run mfc package   --source factcrescendo_ml --version 1

# Not yet implemented:
uv run mfc dedup
uv run mfc all --pilot
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
  discovery/  rss.py                       # RSS / Atom feed -> URL list
  fetch/      client.py cache.py robots.py # async httpx + hishel + robots
  extract/    claimreview.py selectors.py pipeline.py
  normalize/  labels.py script.py dates.py
  corpus/     record.py writer.py          # FactCheckRecord + Parquet writer
  utils/      hashing.py jsonl.py
scripts/validate_sources.py                # standalone config validator
tests/fixtures/                            # (planned) vcrpy cassettes
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

## Citation

If this corpus or pipeline is useful in your work, a citation would be appreciated. GitHub renders a "Cite this repository" widget from [`CITATION.cff`](CITATION.cff); the BibTeX equivalent is:

```bibtex
@misc{bhaskaran_malayalam_factcheck_corpus_2026,
  author       = {Bhaskaran, Hrishikesh},
  title        = {malayalam-factcheck-corpus},
  year         = {2026},
  version      = {1.0},
  howpublished = {\url{https://github.com/stultus/malayalam-factcheck-corpus}},
  note         = {Pipeline and labelled corpus of Malayalam fact-check articles}
}
```

It helps reproducibility if the `version` field reflects the corpus version you actually used (`corpus_v{N}.parquet`) rather than repo HEAD, since re-runs against newer source state produce different records.

The records here are derived from third-party fact-checks, so a citation to the original publishers alongside this one is also appreciated where it fits. The `source_id` column on every record maps to the entries in [`configs/malayalam_factcheck_sources.json`](configs/malayalam_factcheck_sources.json), and the `url` column points to the canonical article — both should be enough to attribute back to the IFCN signatory or media house that did the underlying reporting.

## License

[LICENSE](LICENSE) (MIT) covers the **pipeline code only**. Any released corpus is a separate work — see [LEGAL.md](LEGAL.md) for the recommended corpus license posture.
