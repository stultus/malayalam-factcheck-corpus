# malayalam-factcheck-corpus

A batch pipeline that turns Malayalam fact-check articles from IFCN-certified Indian portals into a versioned Parquet corpus, ready for training claim-verification and misinformation-detection models.

Given `configs/malayalam_factcheck_sources.json`, the pipeline discovers article URLs, fetches them (cached, rate-limited, robots-respecting), extracts structured fields (preferring schema.org `ClaimReview` JSON-LD), normalizes verdicts and dates, dedups claims across sources, and writes `corpus_v{N}.parquet` + a `quarantine_v{N}.parquet` for records that fail validation.

## Status

Scaffolding and config validation are in place. The pipeline stages themselves are not yet implemented.

Currently working:

- Project boots under `uv`, installs cleanly, CLI is discoverable (`mfc --help`).
- `mfc validate-config` and `scripts/validate_sources.py` load and validate the seed JSON against the pydantic schema.
- `ruff`, `ruff format`, and `mypy --strict` pass on the scaffold.

Not yet implemented: `discover`, `fetch`, `extract`, `normalize`, `dedup`, `package`, `all` stages all raise `NotImplementedError`. The vertical slice on `factcrescendo_ml` is the next milestone.

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
uv run mfc --help                          # list stages
uv run mfc validate-config                 # validate the seed JSON

# Once the pipeline is implemented:
uv run mfc all --pilot                     # 50 URLs per source end-to-end
uv run mfc discover --source factcrescendo_ml --limit 5
uv run mfc fetch    --source factcrescendo_ml --limit 5
uv run mfc extract  --source factcrescendo_ml --limit 5
uv run mfc normalize
uv run mfc dedup
uv run mfc package  --version 1
```

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
src/mfc/                                   # package source
  cli.py                                   # typer entrypoint
  config.py                                # SourcesFile, SourceConfig, ...
  corpus/record.py                         # FactCheckRecord
  discovery/ fetch/ extract/ normalize/ dedup/ corpus/ utils/
scripts/validate_sources.py                # standalone config validator
tests/fixtures/                            # vcrpy cassettes + ground-truth records
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

## License

[LICENSE](LICENSE) (MIT) covers the **pipeline code only**. Any released corpus is a separate work — see [LEGAL.md](LEGAL.md) for the recommended corpus license posture.
