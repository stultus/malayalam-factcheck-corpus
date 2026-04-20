"""Standalone script that validates the sources JSON against ``SourcesFile``.

Usage::

    uv run python scripts/validate_sources.py [path]
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError

from mfc.config import SourcesFile

DEFAULT_PATH = Path("configs/malayalam_factcheck_sources.json")


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    try:
        config = SourcesFile.load(path)
    except FileNotFoundError:
        print(f"error: config not found at {path}", file=sys.stderr)
        return 2
    except ValidationError as err:
        print(f"error: {path} failed schema validation", file=sys.stderr)
        print(err, file=sys.stderr)
        return 1

    print(f"ok: {path} validated. {len(config.sources)} sources loaded.")
    for src in config.sources:
        flags = []
        if src.ifcn_signatory:
            flags.append("ifcn")
        if src.meta_partner:
            flags.append("meta")
        label = ", ".join(flags) or "-"
        print(f"  - {src.id:<32} [{src.language}] ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
