# Legal posture

This document captures the legal and ethical constraints that shape what the pipeline collects, what it stores, and what may be redistributed. It is **not** legal advice. If you intend to publish a derived corpus, get a real lawyer to review.

## Jurisdiction

The sources in `configs/malayalam_factcheck_sources.json` are all Indian publishers, so the **Indian Copyright Act 1957** and the **Digital Personal Data Protection Act 2023 (DPDP)** govern. Indian law has no explicit text-and-data-mining exception comparable to the EU DSM Directive (Art. 3–4) or Japan (Art. 30-4). Section 52(1)(a) covers "fair dealing for the purposes of private or personal use, including research" plus criticism and review — narrower than US fair use, and especially narrow once you start redistributing.

## Field-by-field redistribution profile

What the `FactCheckRecord` schema collects, ranked by redistribution risk:

| Field | Risk | Notes |
|---|---|---|
| `url`, `url_canonical`, `published_date`, `crawled_date`, `source_id`, `record_id` | low | Facts; not copyrightable. |
| `language`, `claim_text_script`, `extractor_used`, `extractor_confidence` | low | Derived metadata. |
| `verdict_raw`, `verdict_canonical`, `label_source` | low | The publisher's stated conclusion is a fact about the publisher's act of fact-checking. |
| `claim_text` | low–medium | Typically the viral claim being debunked, often itself a third-party assertion. When sourced from `ClaimReview` JSON-LD, publishers have explicitly marked it for machine consumption — strong implied-license argument. |
| `title` | medium | Editorial work product; usually short. Excerpts under fair dealing are defensible. |
| `evidence_text` | **high** | This is the publisher's full debunking prose. Verbatim reproduction of full article bodies across the corpus crosses from "research" into "substantial reproduction." For any public release, this field must be excerpted, summarized, or replaced with a re-fetch instruction. |

`claim_embedding_hash` and `duplicate_of` are derived fingerprints with no copyright implication.

## What "publish the corpus" can mean

Risk scales with how much of the original work travels with the dataset.

1. **Local research use** — fetch, store, train against. Lowest risk; squarely inside Section 52(1)(a)(i).
2. **Internal model artifacts** — distilled weights, embeddings, classifiers. Low risk; the original prose does not travel.
3. **URLs + structured fields only** — release the corpus as `(url, claim_text, verdict, metadata, snippet)` plus a re-fetch script. The "C4 / Common Crawl" pattern. Acceptable risk for research releases.
4. **Full Parquet with `evidence_text`** — public release of debunking-article bodies. **Do not do this without written permission from each source publisher.**

## Source-specific notes

- **IFCN signatories** (Fact Crescendo, Newschecker, NewsMeter, India Today AFWA): the IFCN code values transparency. Email and ask before any public release — many will say yes for non-commercial research. This is the single largest risk reduction available.
- **PIB Fact Check**: Indian government work. Section 52(1)(q) gives wide latitude for reproduction with attribution. The bigger concern with PIB is the political-bias caveat already documented in `CLAUDE.md` (do not train on PIB alone).
- **Manorama, Mathrubhumi**: traditional newspaper publishers, more aggressive on copyright historically. Treat conservatively; do not redistribute their text without permission.

## Personal data and defamation

Fact-check articles routinely name individuals accused of spreading misinformation.

- **DPDP Act 2023** has implications even for publicly-available personal data. Aggregating named individuals into a redistributable dataset is a separate exposure on top of copyright.
- **Secondary defamation**: re-publishing a publisher's claim that "X spread fake news" can carry liability if the underlying claim is contested.

Mitigations: limit to public figures and to the names already present in the source URL/title; provide a takedown channel; do not attempt to identify private individuals downstream.

## Code license vs corpus license

`LICENSE` (MIT) covers the **pipeline code only**. The corpus produced by running the pipeline is a separate work and inherits its license posture from the source publishers, not from this repo.

Recommended posture for any released corpus:

- **CC BY-NC 4.0** (or stricter) for the structured corpus, with attribution per record.
- A `DATASET-LICENSE.md` shipped alongside the Parquet, stating: research/non-commercial use only, attribution required, takedown policy honoured.
- Do not relicense the underlying article text under any permissive license — you do not own it.

## Operational mitigations baked into the pipeline

These are already in `configs/malayalam_factcheck_sources.json` and `CLAUDE.md`:

- `respect_robots_txt: true` and per-host concurrency limits.
- Identifiable User-Agent with research-purpose statement and contact email.
- 3s default delay; exponential backoff on 429/403 (per design rule 7 in CLAUDE.md).
- HTTP cache to avoid re-hitting sources on re-runs.

To be added when the pipeline is implemented:

- A denylist / takedown registry the `package` stage consults before writing any record to the public corpus tier.
- A "publishable subset" view in the packaging stage that drops or excerpts `evidence_text`.

## Takedown

See `TAKEDOWN.md`.
