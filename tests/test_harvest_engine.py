from __future__ import annotations

from pathlib import Path

from conftest import FakeHttp, make_config, make_source

from harvester.base import BaseConnector
from harvester.harvest import Harvester
from harvester.models import Record
from harvester.registry import register


@register
class _FakeConnector(BaseConnector):
    name = "fake"
    resource_type = "paper"
    description = "test-only connector"

    def iter_records(self):
        for d in self.opt("records", []):
            yield Record(source="fake", resource_type="paper", **d)


def _records(n, with_url=False):
    out = []
    for i in range(n):
        d = {"ext_id": f"id{i}", "title": f"t{i}", "categories": ["cat"]}
        if with_url:
            d["download_url"] = f"http://x/{i}.pdf"
            d["file_ext"] = "pdf"
        out.append(d)
    return out


def _cfg(tmp_path, **src_opts):
    src = make_source("fake", **src_opts)
    return make_config(tmp_path, sources={"fake": src}, **{
        k: src_opts[k] for k in ("download", "global_max_records") if k in src_opts
    })


def test_per_source_cap(tmp_path):
    cfg = _cfg(tmp_path, records=_records(5), max_records=2, download=False)
    h = Harvester(cfg)
    totals = h.run(show_progress=False)
    total = h.storage.total()
    h.close()
    assert totals.get("metadata") == 2
    assert total == 2


def test_resume_skips_processed(tmp_path):
    cfg = _cfg(tmp_path, records=_records(3), download=False)
    Harvester(cfg).run(show_progress=False)
    h2 = Harvester(_cfg(tmp_path, records=_records(3), download=False))
    totals = h2.run(show_progress=False)
    h2.close()
    assert totals.get("skipped") == 3
    assert totals.get("metadata", 0) == 0


def test_dry_run_writes_nothing(tmp_path):
    cfg = _cfg(tmp_path, records=_records(4), download=False)
    h = Harvester(cfg)
    totals = h.run(show_progress=False, dry_run=True)
    total = h.storage.total()
    h.close()
    assert totals.get("preview") == 4
    assert total == 0
    assert list((tmp_path / "catalog").glob("*.jsonl")) == []


def test_global_cap(tmp_path):
    cfg = _cfg(tmp_path, records=_records(5), download=False, global_max_records=2)
    h = Harvester(cfg)
    totals = h.run(show_progress=False)
    h.close()
    assert sum(totals.values()) == 2


def test_catalog_and_state_written(tmp_path):
    cfg = _cfg(tmp_path, records=_records(2), download=False)
    h = Harvester(cfg)
    h.run(show_progress=False)
    h.close()
    catalog = tmp_path / "catalog" / "fake.jsonl"
    assert catalog.exists()
    assert len(catalog.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_download_fallback_uses_alt(tmp_path):
    cfg = _cfg(tmp_path, records=[], download=True)
    h = Harvester(cfg)
    rec = Record(source="fake", ext_id="z", resource_type="paper", categories=["c"],
                 download_url="http://x/primary.pdf", file_ext="pdf",
                 extra={"alt_downloads": [("http://x/backup.txt", "txt")]})
    http = FakeHttp()
    http.fail_urls = {"http://x/primary.pdf"}
    ok = h._download(rec, http)
    h.close()
    assert ok is True
    assert rec.download_url == "http://x/backup.txt"
    assert rec.file_ext == "txt"
    assert rec.bytes == 4 and len(rec.sha256) == 64


def test_download_all_fail_returns_false(tmp_path):
    cfg = _cfg(tmp_path, records=[], download=True)
    h = Harvester(cfg)
    rec = Record(source="fake", ext_id="z", resource_type="paper",
                 download_url="http://x/a.pdf", file_ext="pdf",
                 extra={"alt_downloads": [("http://x/b.txt", "txt")]})
    http = FakeHttp()
    http.fail_urls = {"http://x/a.pdf", "http://x/b.txt"}
    assert h._download(rec, http) is False
    h.close()


def test_events_emitted(tmp_path):
    cfg = _cfg(tmp_path, records=_records(3), download=False)
    events = []
    h = Harvester(cfg)
    h.run(show_progress=False, on_event=events.append)
    h.close()
    types = [e["type"] for e in events]
    assert types[0] == "run_start"
    assert "source_start" in types and "source_done" in types
    assert types[-1] == "run_done"
    records = [e for e in events if e["type"] == "record"]
    assert len(records) == 3
    assert records[0]["status"] == "metadata"
    assert records[0]["category"] == "cat"
    run_done = [e for e in events if e["type"] == "run_done"][0]
    assert run_done["totals"].get("metadata") == 3
    assert run_done["stopped"] is False


def test_should_stop_cancels_midway(tmp_path):
    cfg = _cfg(tmp_path, records=_records(10), download=False)
    seen = {"n": 0}
    events = []

    def on_ev(e):
        events.append(e)
        if e["type"] == "record":
            seen["n"] += 1

    h = Harvester(cfg)
    h.run(show_progress=False, on_event=on_ev, should_stop=lambda: seen["n"] >= 2)
    h.close()
    records = [e for e in events if e["type"] == "record"]
    assert len(records) == 2                      # stopped right after the 2nd
    run_done = [e for e in events if e["type"] == "run_done"][0]
    assert run_done["stopped"] is True
