"""End-to-end tests for the label server's HTTP API.

These tests exercise the real ``ThreadingHTTPServer`` on a free port,
hit it over loopback with stdlib ``urllib``, and tear it down cleanly.
That is the only way to be sure the request handler, JSON I/O, and
storage flush actually compose correctly.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from datetime import UTC, datetime
from http.client import HTTPResponse
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from mfc.label.server import _LabelServer, _load_records
from mfc.label.store import LabelStore


def _sample_records(corpus_path: Path) -> Path:
    rows = [
        {
            "record_id": "rec_1",
            "source_id": "factcrescendo_ml",
            "url": "https://example.test/article-1",
            "url_canonical": None,
            "claim_text": "ഒരു അവകാശവാദം",
            "claim_text_script": "mlym",
            "evidence_text": "ദീർഘമായ വിശദീകരണം ...",
            "title": "Fact Check: ഒരു ശീർഷകം",
            "language": "ml",
            "verdict_raw": "False",
            "verdict_canonical": "false",
            "label_source": "ifcn",
            "published_date": datetime(2026, 1, 15, tzinfo=UTC),
            "crawled_date": datetime(2026, 5, 1, tzinfo=UTC),
            "extractor_used": "css_selectors",
            "extractor_confidence": 0.6,
            "claim_embedding_hash": None,
            "duplicate_of": None,
        },
        {
            "record_id": "rec_2",
            "source_id": "newschecker_ml",
            "url": "https://example.test/article-2",
            "url_canonical": None,
            "claim_text": "Another claim",
            "claim_text_script": "latn",
            "evidence_text": "Evidence body",
            "title": "Another title",
            "language": "ml",
            "verdict_raw": "Misleading",
            "verdict_canonical": "unknown",
            "label_source": "ifcn",
            "published_date": datetime(2026, 2, 1, tzinfo=UTC),
            "crawled_date": datetime(2026, 5, 1, tzinfo=UTC),
            "extractor_used": "claimreview_jsonld",
            "extractor_confidence": 1.0,
            "claim_embedding_hash": None,
            "duplicate_of": None,
        },
    ]
    pl.DataFrame(rows).write_parquet(corpus_path)
    return corpus_path


@pytest.fixture
def running_server(tmp_path: Path) -> Any:
    corpus_path = _sample_records(tmp_path / "corpus_v99.parquet")
    records = _load_records(corpus_path)
    store = LabelStore(tmp_path / "manual_labels.parquet")
    httpd = _LabelServer(("127.0.0.1", 0), store, records, corpus_path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, store, records
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _request(
    method: str, url: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert isinstance(resp, HTTPResponse)
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload
    except urllib.error.HTTPError as err:
        payload = json.loads(err.read().decode("utf-8"))
        return err.code, payload


def _base(server: _LabelServer) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"


def test_records_endpoint_returns_all(running_server: Any) -> None:
    httpd, _store, _records = running_server
    status, payload = _request("GET", f"{_base(httpd)}/api/records")
    assert status == 200
    assert len(payload["records"]) == 2
    ids = {r["record_id"] for r in payload["records"]}
    assert ids == {"rec_1", "rec_2"}
    for rec in payload["records"]:
        assert rec["manual_label"] is None


def test_upsert_persists_and_round_trips(running_server: Any) -> None:
    httpd, store, _records = running_server
    status, payload = _request(
        "POST",
        f"{_base(httpd)}/api/labels",
        body={"record_id": "rec_1", "verdict": "misleading", "notes": "second look"},
    )
    assert status == 200
    assert payload["label"]["verdict"] == "misleading"
    assert payload["label"]["notes"] == "second look"

    saved = store.get("rec_1")
    assert saved is not None
    assert saved.verdict == "misleading"

    _, fetched = _request("GET", f"{_base(httpd)}/api/records")
    by_id = {r["record_id"]: r for r in fetched["records"]}
    assert by_id["rec_1"]["manual_label"]["verdict"] == "misleading"
    assert by_id["rec_2"]["manual_label"] is None


def test_delete_removes_label(running_server: Any) -> None:
    httpd, store, _records = running_server
    _request(
        "POST",
        f"{_base(httpd)}/api/labels",
        body={"record_id": "rec_1", "verdict": "false"},
    )
    status, payload = _request("DELETE", f"{_base(httpd)}/api/labels/rec_1")
    assert status == 200
    assert payload["deleted"] == "rec_1"
    assert store.get("rec_1") is None

    status, _ = _request("DELETE", f"{_base(httpd)}/api/labels/rec_1")
    assert status == 404


def test_upsert_validates_verdict(running_server: Any) -> None:
    httpd, _store, _records = running_server
    status, payload = _request(
        "POST",
        f"{_base(httpd)}/api/labels",
        body={"record_id": "rec_1", "verdict": "bogus"},
    )
    assert status == 400
    assert "invalid label" in payload["error"]


def test_upsert_requires_fields(running_server: Any) -> None:
    httpd, _store, _records = running_server
    status, payload = _request("POST", f"{_base(httpd)}/api/labels", body={"record_id": "rec_1"})
    assert status == 400
    assert "record_id and verdict" in payload["error"]


def test_stats_endpoint_counts_correctly(running_server: Any) -> None:
    httpd, _store, _records = running_server
    _request(
        "POST",
        f"{_base(httpd)}/api/labels",
        body={"record_id": "rec_1", "verdict": "false"},
    )
    status, payload = _request("GET", f"{_base(httpd)}/api/stats")
    assert status == 200
    assert payload["total_records"] == 2
    assert payload["total_labelled"] == 1
    assert payload["by_source"]["newschecker_ml"]["unknown"] == 1
    assert payload["by_source"]["factcrescendo_ml"]["labelled"] == 1


def test_static_file_path_traversal_blocked(running_server: Any) -> None:
    httpd, _store, _records = running_server
    # The literal "/static/../server.py" would be normalised by urllib so we
    # send the suspicious bit URL-encoded; the handler must still reject.
    req = urllib.request.Request(f"{_base(httpd)}/static/%2e%2e/server.py", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 404
    except urllib.error.HTTPError as err:
        assert err.code == 404
