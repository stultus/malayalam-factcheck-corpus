# Datasheet for malayalam-factcheck-corpus

This datasheet follows Gebru et al., *Datasheets for Datasets* (2021),
with data-statement elements from Bender & Friedman (2018). It
describes the v0.1.1 pilot snapshot. Numbers will refresh on each
tagged release; the structural sections (Motivation, Uses,
Distribution, Maintenance) carry forward unchanged unless the
project's posture shifts.

## Motivation

- **Why was this dataset created?** To build a labelled corpus of Malayalam
  fact-check articles from IFCN-certified Indian fact-check portals,
  suitable for training claim-verification and misinformation-detection
  models in a low-resource Indic language.
- **Who funded it?** Independent / unfunded research by Hrishikesh
  Bhaskaran (ORCID 0009-0004-9502-401X).
- **Any specific tasks in mind?** Claim verification, retrieval-augmented
  fact-checking, multilingual misinformation detection.

## Composition

- **What do instances represent?** One instance = one fact-check article
  published by an Indian fact-check organisation. The schema is the
  `FactCheckRecord` pydantic model in `src/mfc/corpus/record.py`.
- **How many instances are there in total?** v0.1.1 pilot: 170 records
  across 6 sources. Per-source counts:

  | source_id | records | label_source | IFCN |
  |---|---:|---|---|
  | `factcrescendo_ml` | 10 | ifcn | yes |
  | `factcrescendo_en_malayalam_tag` | 50 | ifcn | yes |
  | `newsmeter_ml` | 13 | ifcn | yes |
  | `indiatoday_ml_afwa` | 10 | ifcn | yes |
  | `manorama_factcheck` | 50 | media_house | no |
  | `mathrubhumi_factcheck` | 37 | media_house | no |

  Target for v0.2.0 is a full crawl with manual labels for the long
  tail of `verdict_canonical = unknown` records.
- **Does the dataset contain all possible instances or is it a sample?**
  Sample. The pipeline runs against the disclosed sitemaps / RSS feeds /
  category pages of each source. No comprehensive crawl yet.
- **What data does each instance consist of?** URL + canonical URL + title
  + claim text + evidence text + verdict (raw + canonical) + label
  source + published / crawled timestamps + extractor provenance + script
  detection + dedup metadata.
- **Is there a label or target?** Yes — `verdict_canonical` ∈ {`false`,
  `misleading`, `partly_false`, `true`, `unverified`, `satire`,
  `unknown`}. `label_source` distinguishes auto-extracted, manually
  reviewed, IFCN, government, and weakly labelled origins. v0.1.1
  verdict distribution: 18 `false`, 2 `misleading`, 150 `unknown`,
  0 in the other classes.
- **Is anything missing from individual instances?** `verdict_canonical`
  falls back to `unknown` when the publisher buries the verdict in prose
  rather than a structured field. In v0.1.1 this affects 150 / 170
  records (88%), almost all of them from `manorama_factcheck`,
  `mathrubhumi_factcheck`, and the readability-extracted Fact Crescendo
  English subset. Manual labelling (`mfc label`) and a planned
  Malayalam prose-verdict classifier are the mitigations.
- **Are there relationships between individual instances?** Yes — semantic
  dedup clusters claims across sources. `duplicate_of` points to the
  earliest-published instance in each cluster. In v0.1.1, 123 / 170
  records (72%) are cluster representatives (`duplicate_of IS NULL`)
  and 47 are duplicates of an earlier record. The training-split filter
  is `duplicate_of IS NULL`.
- **Script and language distribution.** v0.1.1: 79 records `mlym`
  (pure Malayalam), 32 `mixed` (Manglish), 59 `latn` (almost entirely
  the English-language Fact Crescendo Kerala-tag subset). `language`
  field: 120 `ml`, 50 `en`, 0 `multi`.
- **Are there recommended data splits?** Time-based only. Random splits
  leak future claims into training. Sort by `published_date`, train =
  oldest 70%, val = next 15%, test = newest 15%.
- **Are there errors, sources of noise, or redundancies?** Yes, several
  known classes (per-source accuracy measurements pending vcrpy
  cassettes — see "Maintenance"):
  - **Verdict ambiguity from prose-buried verdicts.** 88% of v0.1.1
    records carry `verdict_canonical = unknown` because the publisher
    did not expose the verdict in a structured field. The label is not
    *wrong*, it is *missing*; the raw `evidence_text` still contains
    the truth value.
  - **Extractor mix is skewed.** v0.1.1 was extracted via
    `claimreview_jsonld` (10), `css_selectors` (10), and
    `readability` (150). Readability extraction is best-effort
    full-page text — it captures evidence well but fails to isolate
    `claim_text` cleanly, so claim fields from those records are
    noisier than from the structured paths.
  - **Cross-source duplicate redundancy.** 47 / 170 records cluster
    onto an earlier instance of the same claim. They are kept in the
    full corpus for analysis but excluded from training via
    `duplicate_of IS NULL`.
  - **No known instance-level corrections yet.** Manual labelling has
    not surfaced extractor bugs; this section will grow as
    `mfc label` use accumulates.
- **Does the dataset contain confidential or offensive content?** Fact-check
  articles routinely cite slurs, communal claims, and graphic imagery
  (verbatim, in order to debunk). Downstream consumers should expect
  toxic / sensitive surface content.

## Collection process

- **How was the data acquired?** Crawled from the public web using a
  resumable async pipeline (`mfc all`). Discovery via RSS, XML sitemaps,
  or HTML category pages depending on what each source exposes.
- **Sampling strategy.** Newest-first per source, capped at 50 URLs
  in pilot mode (`mfc all --pilot`). Full mode (`mfc all`) walks the
  source's full disclosed sitemap / RSS / category pages with the
  per-source `article_url_pattern` filter applied. Discovery is
  resumable: re-running discover diffs against the previous URL
  manifest, so subsequent crawls only fetch newly-published articles.
- **Time frame.** v0.1.1 records span `published_date` from 2021-05-30
  to 2026-04-30 (the day before the snapshot). The distribution is
  heavily right-skewed because pilot mode samples newest-first per
  source. A full crawl is expected to reach back to each publisher's
  earliest archived fact-check (2017-2019 for the IFCN signatories);
  this section will be updated with a histogram per source after the
  v0.2.0 full crawl.
- **Were any ethical review processes conducted?** No formal IRB review —
  this is unfunded independent research; the data comes from
  intentionally-public fact-check journalism. The legal posture
  (copyright, DPDP Act 2023, defamation) is documented in `LEGAL.md`.
- **Did individuals consent?** Public-interest journalism does not
  generally require subject consent. This corpus does not augment,
  identify, link, or enrich records against named individuals, and is
  not released for any use that would enable such identification. See
  the "Personal data" section of [LEGAL.md](LEGAL.md), which is
  informed by India's Digital Personal Data Protection Act 2023.

## Preprocessing / cleaning / labelling

- **Verdict canonicalisation.** Longest-alias-wins string match against
  `canonical_labels` in `configs/malayalam_factcheck_sources.json`.
- **Date parsing.** `dateparser` with `languages=['ml', 'en']` and
  `TIMEZONE='Asia/Kolkata'`, normalised to UTC.
- **Script detection.** ≥80% Malayalam Unicode → `mlym`, ≥80% Latin →
  `latn`, otherwise `mixed`.
- **Deduplication.** Multilingual sentence-transformer embeddings
  (`paraphrase-multilingual-mpnet-base-v2`) on `claim_text`, greedy
  cosine clustering at threshold 0.85. Earliest `published_date` in
  each cluster wins.
- **Manual labelling.** Browser-based labelling tool (`mfc label`)
  writes to a sidecar parquet that the `package` stage joins in,
  overriding `verdict_canonical` and setting `label_source = "manual"`.
- **Was the raw data saved?** Yes — raw HTML is cached under
  `data/raw/html/` and HTTP responses under `data/raw/http_cache/`.

## Uses

- **What tasks has it been used for?** None yet — corpus is in initial
  build phase.
- **What other tasks could it be used for?** Cross-lingual claim
  matching, retrieval-augmented generation evaluation, misinformation
  detection benchmarking, Malayalam NLP pretraining augmentation.
- **Are there tasks it should NOT be used for?** Don't use it as a
  general-purpose Malayalam corpus — fact-check articles are
  topically and stylistically narrow. Don't train a "is this user
  spreading misinformation" classifier on it; the labels apply to
  *claims*, not to *people*. PIB Fact Check is ideologically skewed —
  always mix it with other sources and keep `label_source` as a
  feature.

## Distribution

- **Will the dataset be distributed to third parties?** Yes — eventually,
  but in tiers. The pipeline code (this repository, MIT) is already
  public. The corpus itself is gated on per-source publisher
  permissions. The `mfc package --tier publishable` command emits a
  parquet that drops records from any source whose `permission_status`
  is not `granted`, and replaces `evidence_text` with the first 280
  characters plus a re-fetch hint. Sources upgrade to `granted` only
  after the publisher confirms in writing (see `docs/outreach/`).
  The matching `mfc rehydrate` script lets a consumer rebuild the
  full corpus on their own machine from the published URL list by
  re-fetching each source page and re-running the extractor pipeline.
- **Current distribution status.** As of v0.1.1, every configured
  source is `permission_status = unasked`, so the publishable tier
  is intentionally empty and no corpus parquet has been released.
  The pipeline code and this datasheet are the only public artefacts
  until outreach concludes.
- **License.** Code: MIT. Released corpus: CC BY-NC 4.0 or stricter,
  per source permission. See `LEGAL.md`.
- **DOI.** Concept DOI 10.5281/zenodo.19940702 (resolves to latest);
  v0.1.1 version DOI 10.5281/zenodo.19940703.
- **Subject to export controls or other restrictions?** No.

## Maintenance

- **Maintainer.** Hrishikesh Bhaskaran (hello@stultus.in).
- **How will updates be communicated?** Tagged GitHub releases plus a
  fresh Zenodo version DOI per release.
- **Will old versions be supported?** Yes — Zenodo retains every
  version DOI. The README / CITATION.cff document the latest.
- **Erratum / takedown process.** See `TAKEDOWN.md`. Takedown requests
  feed an internal denylist that the `package` stage consults before
  writing publishable tiers.
