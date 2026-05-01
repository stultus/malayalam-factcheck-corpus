"""Localhost-only HTTP server for browser-based manual labelling.

The terminal is the wrong surface for Malayalam: glyph composition,
chillu, and reordering vowel signs are inconsistently rendered across
terminal emulators. The browser handles all of this correctly using
the system font stack, so the labelling UI lives there.

Server is bound to 127.0.0.1 only and uses ``ThreadingHTTPServer`` so
a slow request never blocks the next click. There is no auth — this
is a single-user local tool, not a deployed service.
"""

from __future__ import annotations

import json
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import polars as pl
from loguru import logger

from mfc.label.store import LabelStore
from mfc.paths import PROCESSED_ROOT

_STATIC_DIR = Path(__file__).parent / "static"


def latest_corpus_path() -> Path | None:
    """Return the highest-versioned ``corpus_v{N}.parquet`` under ``data/processed/``."""
    if not PROCESSED_ROOT.exists():
        return None
    candidates = sorted(
        PROCESSED_ROOT.glob("corpus_v*.parquet"),
        key=lambda p: int(p.stem.removeprefix("corpus_v")),
    )
    return candidates[-1] if candidates else None


def _load_records(path: Path) -> list[dict[str, Any]]:
    frame = pl.read_parquet(path)
    rows: list[dict[str, Any]] = []
    for row in frame.iter_rows(named=True):
        rows.append(
            {
                "record_id": row["record_id"],
                "source_id": row["source_id"],
                "url": row["url"],
                "title": row["title"],
                "claim_text": row["claim_text"],
                "evidence_text": row["evidence_text"],
                "verdict_raw": row["verdict_raw"],
                "verdict_canonical": row["verdict_canonical"],
                "language": row["language"],
                "claim_text_script": row["claim_text_script"],
                "extractor_used": row["extractor_used"],
                "published_date": (
                    row["published_date"].isoformat()
                    if isinstance(row["published_date"], datetime)
                    else str(row["published_date"])
                ),
            }
        )
    return rows


class _Handler(BaseHTTPRequestHandler):
    server: _LabelServer

    def log_message(self, format: str, *args: Any) -> None:
        # Silence stderr access logs; loguru handles structured logging elsewhere.
        return

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if url.path == "/api/records":
            self._serve_records()
            return
        if url.path == "/api/labels":
            self._serve_labels()
            return
        if url.path == "/api/stats":
            self._serve_stats()
            return
        if url.path.startswith("/static/"):
            name = url.path.removeprefix("/static/")
            self._serve_static(name)
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/labels":
            self._upsert_label()
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_DELETE(self) -> None:
        url = urlsplit(self.path)
        if url.path.startswith("/api/labels/"):
            record_id = url.path.removeprefix("/api/labels/")
            self._delete_label(record_id)
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    # --- handlers ---

    def _serve_records(self) -> None:
        records = self.server.records
        labels = self.server.store.all()
        out = []
        for rec in records:
            label = labels.get(rec["record_id"])
            out.append(
                {
                    **rec,
                    "manual_label": label.model_dump(mode="json") if label else None,
                }
            )
        self._json(HTTPStatus.OK, {"records": out, "corpus_path": str(self.server.corpus_path)})

    def _serve_labels(self) -> None:
        labels = self.server.store.all()
        self._json(
            HTTPStatus.OK,
            {"labels": [label.model_dump(mode="json") for label in labels.values()]},
        )

    def _serve_stats(self) -> None:
        records = self.server.records
        labels = self.server.store.all()
        by_source: dict[str, dict[str, int]] = {}
        for rec in records:
            sid = rec["source_id"]
            entry = by_source.setdefault(sid, {"total": 0, "labelled": 0, "unknown": 0})
            entry["total"] += 1
            if rec["record_id"] in labels:
                entry["labelled"] += 1
            if rec["verdict_canonical"] == "unknown":
                entry["unknown"] += 1
        self._json(
            HTTPStatus.OK,
            {
                "total_records": len(records),
                "total_labelled": len(labels),
                "by_source": by_source,
            },
        )

    def _upsert_label(self) -> None:
        body = self._read_json()
        if body is None:
            return
        record_id = body.get("record_id")
        verdict = body.get("verdict")
        if not record_id or not verdict:
            self._error(HTTPStatus.BAD_REQUEST, "record_id and verdict are required")
            return
        try:
            label = self.server.store.upsert(record_id, verdict, notes=body.get("notes"))
        except Exception as err:
            self._error(HTTPStatus.BAD_REQUEST, f"invalid label: {err}")
            return
        self._json(HTTPStatus.OK, {"label": label.model_dump(mode="json")})

    def _delete_label(self, record_id: str) -> None:
        if self.server.store.delete(record_id):
            self._json(HTTPStatus.OK, {"deleted": record_id})
        else:
            self._error(HTTPStatus.NOT_FOUND, "no such label")

    # --- low-level I/O ---

    def _serve_static(self, name: str, content_type: str | None = None) -> None:
        path = _STATIC_DIR / name
        if not path.is_file() or _STATIC_DIR not in path.resolve().parents:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        body = path.read_bytes()
        ctype = content_type or _guess_content_type(path)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            self._error(HTTPStatus.BAD_REQUEST, "empty body")
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as err:
            self._error(HTTPStatus.BAD_REQUEST, f"invalid json: {err}")
            return None
        if not isinstance(data, dict):
            self._error(HTTPStatus.BAD_REQUEST, "json body must be an object")
            return None
        return data


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }.get(suffix, "application/octet-stream")


class _LabelServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        store: LabelStore,
        records: list[dict[str, Any]],
        corpus_path: Path,
    ) -> None:
        super().__init__(address, _Handler)
        self.store = store
        self.records = records
        self.corpus_path = corpus_path


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
) -> None:
    """Start the label server. Blocks until Ctrl-C."""
    corpus_path = latest_corpus_path()
    if corpus_path is None:
        raise RuntimeError(
            "no corpus parquet found under data/processed/. "
            "Run `mfc all --pilot` (or the per-stage commands) first."
        )
    records = _load_records(corpus_path)
    store = LabelStore()
    httpd = _LabelServer((host, port), store, records, corpus_path)
    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}/"
    logger.info(
        "label server listening",
        url=url,
        records=len(records),
        existing_labels=len(store),
        corpus=str(corpus_path),
    )
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down label server")
    finally:
        httpd.server_close()
