"""Typer entrypoint exposing each pipeline stage as a subcommand."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from loguru import logger
from pydantic import ValidationError

from mfc.config import SourceConfig, SourcesFile
from mfc.corpus.record import FactCheckRecord, LabelSource
from mfc.corpus.writer import write_parquet
from mfc.discovery.category import fetch_category_urls
from mfc.discovery.rss import fetch_rss_urls
from mfc.discovery.sitemap import fetch_sitemap_urls
from mfc.extract.base import ExtractResult
from mfc.extract.pipeline import run_extractors
from mfc.fetch.client import RobotsDisallowed, open_fetch_client
from mfc.normalize.dates import parse_date
from mfc.normalize.labels import canonical_verdict
from mfc.normalize.script import detect_script
from mfc.paths import (
    DEDUPED_PATH,
    PROCESSED_ROOT,
    RAW_ROOT,
    ensure_dir,
    fetched_path,
    records_path,
    urls_path,
)
from mfc.utils.hashing import url_hash
from mfc.utils.jsonl import read_jsonl, write_jsonl

app = typer.Typer(
    name="mfc",
    help="Build a Malayalam fact-check corpus from IFCN-certified sources.",
    no_args_is_help=True,
)

DEFAULT_CONFIG = Path("configs/malayalam_factcheck_sources.json")


def _load_config(path: Path) -> SourcesFile:
    try:
        return SourcesFile.load(path)
    except FileNotFoundError:
        typer.echo(f"error: config not found at {path}", err=True)
        raise typer.Exit(code=2) from None
    except ValidationError as err:
        typer.echo(f"error: {path} failed schema validation", err=True)
        typer.echo(str(err), err=True)
        raise typer.Exit(code=1) from None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _label_source(src: SourceConfig) -> LabelSource:
    if src.ifcn_signatory:
        return "ifcn"
    if src.publisher_org and "Government" in src.publisher_org:
        return "government"
    return "media_house"


def _html_path(source_id: str, record_id: str) -> Path:
    return RAW_ROOT / "html" / source_id / f"{record_id}.html"


@app.command("validate-config")
def validate_config(
    path: Annotated[
        Path, typer.Option("--path", "-p", help="Path to the sources JSON.")
    ] = DEFAULT_CONFIG,
) -> None:
    """Sanity-check the seed JSON against the SourceConfig schema."""
    config = _load_config(path)
    ifcn_count = sum(1 for s in config.sources if s.ifcn_signatory)
    typer.echo(
        f"ok: {path} — {len(config.sources)} sources ({ifcn_count} IFCN-certified), "
        f"schema_version={config.schema_version}"
    )


@app.command()
def discover(
    source: Annotated[str, typer.Option("--source", "-s", help="Source id to discover.")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap URLs for pilot runs.")] = None,
) -> None:
    """Stage 1: list article URLs via RSS, sitemap, or category pages."""
    config = _load_config(DEFAULT_CONFIG)
    src = config.source(source)
    if (
        src.discovery.rss is None
        and src.discovery.sitemap is None
        and not src.discovery.category_pages
    ):
        typer.echo(
            f"error: source {source} has no rss, sitemap, or category_pages configured",
            err=True,
        )
        raise typer.Exit(code=2)

    urls = asyncio.run(_run_discover(config, src, limit))

    rows = [{"url": u, "discovered_at": _now_iso()} for u in urls]
    written = write_jsonl(urls_path(source), rows)
    typer.echo(f"discover: {source} -> {written} urls -> {urls_path(source)}")


def _section_prefix(src: SourceConfig) -> str | None:
    # When article_url_pattern is set it's the precise filter; the broader
    # path-prefix would only over-constrain (e.g. when a section is split
    # across several sub-pages whose URLs share no common ancestor).
    if src.discovery.article_url_pattern is not None:
        return None
    if src.malayalam_section is not None:
        return str(src.malayalam_section)
    if src.discovery.category_pages:
        return str(src.discovery.category_pages[0])
    return None


def _source_headers(src: SourceConfig) -> dict[str, str] | None:
    if src.user_agent is None:
        return None
    return {"User-Agent": src.user_agent}


async def _run_discover(config: SourcesFile, src: SourceConfig, limit: int | None) -> list[str]:
    headers = _source_headers(src)
    pattern = src.discovery.article_url_pattern
    async with open_fetch_client(config.global_crawler_policy) as client:
        if src.discovery.rss is not None:
            urls = await fetch_rss_urls(client, str(src.discovery.rss), headers=headers)
            return urls if limit is None else urls[:limit]

        if src.discovery.sitemap is not None:
            return await fetch_sitemap_urls(
                client,
                str(src.discovery.sitemap),
                url_prefix=_section_prefix(src),
                url_pattern=pattern,
                max_urls=limit,
                headers=headers,
            )

        return await fetch_category_urls(
            client,
            [str(u) for u in src.discovery.category_pages],
            url_prefix=_section_prefix(src),
            url_pattern=pattern,
            max_urls=limit,
            headers=headers,
        )


@app.command()
def fetch(
    source: Annotated[str, typer.Option("--source", "-s")],
    limit: Annotated[int | None, typer.Option("--limit")] = None,
) -> None:
    """Stage 2: download URLs with caching, rate-limiting, and robots.txt respect."""
    config = _load_config(DEFAULT_CONFIG)
    src = config.source(source)

    urls_file = urls_path(source)
    if not urls_file.exists():
        typer.echo(f"error: run discover first; missing {urls_file}", err=True)
        raise typer.Exit(code=2)

    entries = list(read_jsonl(urls_file))
    if limit is not None:
        entries = entries[:limit]

    rows = asyncio.run(_run_fetch(config, src, entries))
    written = write_jsonl(fetched_path(source), rows)
    typer.echo(f"fetch: {source} -> {written}/{len(entries)} pages -> {fetched_path(source)}")


async def _run_fetch(
    config: SourcesFile, src: SourceConfig, entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    headers = _source_headers(src)
    source_id = src.id
    async with open_fetch_client(config.global_crawler_policy) as client:
        for entry in entries:
            url = entry["url"]
            rid = url_hash(url)
            try:
                response = await client.get(url, headers=headers)
            except RobotsDisallowed:
                logger.warning("robots disallowed", source=source_id, url=url)
                continue
            except Exception as err:
                logger.warning("fetch failed", source=source_id, url=url, error=str(err))
                continue

            html_path = _html_path(source_id, rid)
            ensure_dir(html_path.parent)
            html_path.write_text(response.text, encoding="utf-8")
            rows.append(
                {
                    "url": url,
                    "record_id": rid,
                    "status": response.status_code,
                    "fetched_at": _now_iso(),
                    "html_path": str(html_path),
                }
            )
    return rows


@app.command()
def extract(
    source: Annotated[str, typer.Option("--source", "-s")],
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Stage 3: extract raw fields via JSON-LD (selectors + readability deferred)."""
    config = _load_config(DEFAULT_CONFIG)
    src = config.source(source)

    fetched_file = fetched_path(source)
    if not fetched_file.exists():
        typer.echo(f"error: run fetch first; missing {fetched_file}", err=True)
        raise typer.Exit(code=2)

    fetched = list(read_jsonl(fetched_file))
    if limit is not None:
        fetched = fetched[:limit]

    rows: list[dict[str, Any]] = []
    skipped = 0
    for entry in fetched:
        html = Path(entry["html_path"]).read_text(encoding="utf-8")
        result = run_extractors(html, entry["url"], src)
        if result is None:
            skipped += 1
            logger.warning(
                "extract skipped: no extractor matched",
                source_id=source,
                url=entry["url"],
            )
            continue
        rows.append(
            {
                "url": entry["url"],
                "record_id": entry["record_id"],
                "fetched_at": entry["fetched_at"],
                "extract": result.model_dump(mode="json"),
            }
        )

    if dry_run:
        typer.echo(f"extract dry-run: {source} -> {len(rows)} extracted, {skipped} skipped")
        return

    written = write_jsonl(records_path(source), rows)
    typer.echo(
        f"extract: {source} -> {written} extracted, {skipped} skipped -> {records_path(source)}"
    )


@app.command()
def normalize(
    source: Annotated[str, typer.Option("--source", "-s")],
) -> None:
    """Stage 4: canonicalize verdicts, dates, URLs, script, into FactCheckRecord JSON."""
    config = _load_config(DEFAULT_CONFIG)
    src = config.source(source)
    label_source = _label_source(src)

    records_file = records_path(source)
    if not records_file.exists():
        typer.echo(f"error: run extract first; missing {records_file}", err=True)
        raise typer.Exit(code=2)

    raw = list(read_jsonl(records_file))
    normalized: list[dict[str, Any]] = []
    skipped = 0
    for entry in raw:
        result = ExtractResult.model_validate(entry["extract"])
        record = _to_record(
            entry=entry,
            extract=result,
            source=src,
            label_source=label_source,
            label_lookup=config.canonical_labels,
        )
        if record is None:
            skipped += 1
            continue
        normalized.append(record.model_dump(mode="json"))

    written = write_jsonl(records_file, normalized)
    typer.echo(f"normalize: {source} -> {written} records, {skipped} skipped -> {records_file}")


def _to_record(
    *,
    entry: dict[str, Any],
    extract: ExtractResult,
    source: SourceConfig,
    label_source: LabelSource,
    label_lookup: dict[str, list[str]],
) -> FactCheckRecord | None:
    published = parse_date(extract.published_date_raw)
    if published is None:
        logger.warning(
            "normalize skipped: unparseable date",
            source_id=source.id,
            url=entry["url"],
            raw=extract.published_date_raw,
        )
        return None

    fetched_at = datetime.fromisoformat(entry["fetched_at"])
    verdict_canonical = canonical_verdict(extract.verdict_raw, label_lookup)

    payload: dict[str, Any] = {
        "record_id": entry["record_id"],
        "source_id": source.id,
        "url": entry["url"],
        "url_canonical": extract.url_canonical,
        "claim_text": extract.claim_text,
        "claim_text_script": detect_script(extract.claim_text),
        "evidence_text": extract.evidence_text,
        "title": extract.title,
        "language": source.language,
        "verdict_raw": extract.verdict_raw,
        "verdict_canonical": verdict_canonical,
        "label_source": label_source,
        "published_date": published,
        "crawled_date": fetched_at,
        "extractor_used": extract.extractor_used,
        "extractor_confidence": extract.extractor_confidence,
    }

    try:
        return FactCheckRecord.model_validate(payload)
    except ValidationError as err:
        logger.warning(
            "normalize skipped: validation failed",
            source_id=source.id,
            url=entry["url"],
            error=str(err),
        )
        return None


@app.command()
def dedup(
    threshold: Annotated[
        float, typer.Option("--threshold", help="Cosine similarity threshold.")
    ] = 0.85,
) -> None:
    """Stage 5: cluster claims across sources, mark duplicates of the earliest."""
    from mfc.dedup.semantic import assign_duplicates

    config = _load_config(DEFAULT_CONFIG)
    records: list[FactCheckRecord] = []
    for src in config.sources:
        path = records_path(src.id)
        if not path.exists():
            continue
        for row in read_jsonl(path):
            records.append(FactCheckRecord.model_validate(row))

    if not records:
        typer.echo("dedup: no records found; run normalize first", err=True)
        raise typer.Exit(code=2)

    deduped = assign_duplicates(records, threshold=threshold)
    rows = [r.model_dump(mode="json") for r in deduped]
    written = write_jsonl(DEDUPED_PATH, rows)
    cluster_count = sum(1 for r in deduped if r.duplicate_of is None)
    typer.echo(
        f"dedup: {written} records, {cluster_count} clusters, "
        f"{written - cluster_count} duplicates -> {DEDUPED_PATH}"
    )


@app.command()
def package(
    version: Annotated[int, typer.Option("--version", "-v", help="Corpus version number.")],
    source: Annotated[str | None, typer.Option("--source", "-s")] = None,
) -> None:
    """Stage 6: validate records and write Parquet (deduped output by default)."""
    from mfc.label.store import LabelStore

    config = _load_config(DEFAULT_CONFIG)

    all_records: list[FactCheckRecord] = []
    if source is None and DEDUPED_PATH.exists():
        for row in read_jsonl(DEDUPED_PATH):
            all_records.append(FactCheckRecord.model_validate(row))
    else:
        sources = [config.source(source)] if source else config.sources
        for src in sources:
            path = records_path(src.id)
            if not path.exists():
                logger.warning("package: skipping source with no records", source_id=src.id)
                continue
            for row in read_jsonl(path):
                all_records.append(FactCheckRecord.model_validate(row))

    manual_labels = LabelStore().all()
    overridden = 0
    if manual_labels:
        merged: list[FactCheckRecord] = []
        for record in all_records:
            label = manual_labels.get(record.record_id)
            # needs_review is a sidecar-only flag; it does not map to any
            # canonical verdict and so cannot override the auto verdict.
            if label is None or label.verdict == "needs_review":
                merged.append(record)
                continue
            merged.append(
                record.model_copy(
                    update={
                        "verdict_canonical": label.verdict,
                        "label_source": "manual",
                    }
                )
            )
            overridden += 1
        all_records = merged

    out = PROCESSED_ROOT / f"corpus_v{version}.parquet"
    written = write_parquet(all_records, out)
    typer.echo(
        f"package: {written} rows -> {out}"
        + (f" ({overridden} manual overrides)" if overridden else "")
    )


label_app = typer.Typer(
    name="label",
    help="Manual labelling tool (browser UI; the terminal renders Malayalam poorly).",
    no_args_is_help=False,
    invoke_without_command=True,
)
app.add_typer(label_app)


@label_app.callback()
def label_default(
    ctx: typer.Context,
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="0 picks a free port.")] = 0,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't auto-open.")] = False,
) -> None:
    """Start the localhost labelling server (default subcommand)."""
    if ctx.invoked_subcommand is not None:
        return
    from mfc.label.server import serve

    try:
        serve(host=host, port=port, open_browser=not no_browser)
    except RuntimeError as err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(code=2) from None


@label_app.command("stats")
def label_stats() -> None:
    """Print a one-line summary of the manual-labels sidecar."""
    from collections import Counter

    from mfc.label.store import LabelStore

    labels = LabelStore().all()
    if not labels:
        typer.echo("label stats: no manual labels yet")
        return
    counts = Counter(label.verdict for label in labels.values())
    breakdown = ", ".join(f"{v}={n}" for v, n in sorted(counts.items()))
    typer.echo(f"label stats: {len(labels)} labels ({breakdown})")


@label_app.command("export")
def label_export(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output JSON path.")],
) -> None:
    """Dump the manual labels sidecar as a JSON array."""
    import json

    from mfc.label.store import LabelStore

    labels = LabelStore().all()
    rows = [label.model_dump(mode="json") for label in labels.values()]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"label export: {len(rows)} labels -> {out}")


@app.command("all")
def run_all(
    pilot: Annotated[bool, typer.Option("--pilot", help="Cap to 50 URLs per source.")] = False,
    version: Annotated[int, typer.Option("--version", "-v")] = 1,
) -> None:
    """Run every stage end-to-end across every configured source."""
    config = _load_config(DEFAULT_CONFIG)
    limit = 50 if pilot else None

    for src in config.sources:
        try:
            _run_source(config, src, limit=limit)
        except Exception as err:
            logger.warning("all: source failed; continuing", source_id=src.id, error=str(err))

    dedup()
    package(version=version)


def _run_source(config: SourcesFile, src: SourceConfig, *, limit: int | None) -> None:
    if (
        src.discovery.rss is None
        and src.discovery.sitemap is None
        and not src.discovery.category_pages
    ):
        logger.warning(
            "all: skipping source with no rss, sitemap, or category_pages",
            source_id=src.id,
        )
        return

    urls = asyncio.run(_run_discover(config, src, limit))
    write_jsonl(urls_path(src.id), [{"url": u, "discovered_at": _now_iso()} for u in urls])

    fetched = asyncio.run(
        _run_fetch(config, src, [{"url": u} for u in urls]),
    )
    write_jsonl(fetched_path(src.id), fetched)

    extracted: list[dict[str, Any]] = []
    for entry in fetched:
        html = Path(entry["html_path"]).read_text(encoding="utf-8")
        result = run_extractors(html, entry["url"], src)
        if result is None:
            logger.warning("all: extract skipped", source_id=src.id, url=entry["url"])
            continue
        extracted.append(
            {
                "url": entry["url"],
                "record_id": entry["record_id"],
                "fetched_at": entry["fetched_at"],
                "extract": result.model_dump(mode="json"),
            }
        )

    label_source = _label_source(src)
    normalized: list[dict[str, Any]] = []
    for entry in extracted:
        result = ExtractResult.model_validate(entry["extract"])
        record = _to_record(
            entry=entry,
            extract=result,
            source=src,
            label_source=label_source,
            label_lookup=config.canonical_labels,
        )
        if record is not None:
            normalized.append(record.model_dump(mode="json"))

    write_jsonl(records_path(src.id), normalized)
    typer.echo(
        f"all[{src.id}]: {len(urls)} urls -> {len(fetched)} fetched -> "
        f"{len(extracted)} extracted -> {len(normalized)} normalized"
    )


if __name__ == "__main__":
    app()
