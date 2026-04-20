"""Typer entrypoint exposing each pipeline stage as a subcommand."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="mfc",
    help="Build a Malayalam fact-check corpus from IFCN-certified sources.",
    no_args_is_help=True,
)

DEFAULT_CONFIG = Path("configs/malayalam_factcheck_sources.json")


@app.command("validate-config")
def validate_config(
    path: Annotated[
        Path, typer.Option("--path", "-p", help="Path to the sources JSON.")
    ] = DEFAULT_CONFIG,
) -> None:
    """Sanity-check the seed JSON against the SourceConfig schema."""
    raise NotImplementedError("validate-config is not implemented yet")


@app.command()
def discover(
    source: Annotated[str, typer.Option("--source", "-s", help="Source id to discover.")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap URLs for pilot runs.")] = None,
) -> None:
    """Stage 1: list article URLs for a source via sitemap/RSS/category pages."""
    raise NotImplementedError("discover is not implemented yet")


@app.command()
def fetch(
    source: Annotated[str, typer.Option("--source", "-s")],
    limit: Annotated[int | None, typer.Option("--limit")] = None,
) -> None:
    """Stage 2: download URLs with caching, rate-limiting, and robots.txt respect."""
    raise NotImplementedError("fetch is not implemented yet")


@app.command()
def extract(
    source: Annotated[str, typer.Option("--source", "-s")],
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Stage 3: extract FactCheckRecord fields via JSON-LD, selectors, or readability."""
    raise NotImplementedError("extract is not implemented yet")


@app.command()
def normalize() -> None:
    """Stage 4: canonicalize verdicts, dates, URLs, script detection."""
    raise NotImplementedError("normalize is not implemented yet")


@app.command()
def dedup() -> None:
    """Stage 5: semantic dedup of claims across sources."""
    raise NotImplementedError("dedup is not implemented yet")


@app.command()
def package(
    version: Annotated[int, typer.Option("--version", "-v", help="Corpus version number.")],
) -> None:
    """Stage 6: validate and write Parquet corpus + quarantine tables."""
    raise NotImplementedError("package is not implemented yet")


@app.command("all")
def run_all(
    pilot: Annotated[bool, typer.Option("--pilot", help="Cap to 50 URLs per source.")] = False,
    version: Annotated[int, typer.Option("--version", "-v")] = 1,
) -> None:
    """Run every stage end-to-end."""
    raise NotImplementedError("all is not implemented yet")


if __name__ == "__main__":
    app()
