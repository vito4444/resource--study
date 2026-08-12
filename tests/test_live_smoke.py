"""Opt-in live smoke tests. Run with: pytest -m live

These hit real endpoints and are skipped by default (`-m 'not live'`).
"""
from __future__ import annotations

import pytest

from conftest import make_config, make_source

from harvester.connectors.arxiv import ArxivConnector
from harvester.connectors.gutenberg import GutenbergConnector
from harvester.http import HttpClient

pytestmark = pytest.mark.live


def _http(rate=1.0):
    return HttpClient(contact_email="smoke@example.com", timeout=60, retries=3, rate_limit_seconds=rate)


def test_arxiv_live(tmp_path):
    c = ArxivConnector(make_source("arxiv", categories=["cs.AI"], max_records=2),
                       make_config(tmp_path), _http(3.0))
    recs = list(c.iter_records())
    assert len(recs) == 2
    assert all(r.download_url and r.file_ext == "pdf" for r in recs)


def test_gutenberg_live_download(tmp_path):
    http = _http(1.0)
    c = GutenbergConnector(make_source("gutenberg", languages=["en"], formats=["txt"], max_records=1),
                           make_config(tmp_path), http)
    rec = next(iter(c.iter_records()))
    size, sha = http.download(rec.download_url, tmp_path / "book.txt")
    assert size > 0 and len(sha) == 64
