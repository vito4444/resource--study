from __future__ import annotations

from pathlib import Path

from harvester.models import Record
from harvester.storage import Storage, category_path, sanitize_segment


def test_sanitize_blocks_traversal_and_separators():
    assert sanitize_segment("../../etc/passwd") == "etc-passwd"
    assert sanitize_segment("a/b\\c") == "a-b-c"
    assert sanitize_segment("..") == "unknown"
    assert sanitize_segment("") == "unknown"
    assert sanitize_segment("   ") == "unknown"


def test_sanitize_bounds_length():
    seg = sanitize_segment("x" * 500)
    assert len(seg) <= 80


def test_category_path_joins_segments():
    assert category_path(["cs", "AI"]) == Path("cs") / "AI"
    assert category_path([]) == Path("uncategorized")
    assert category_path(["../evil", "ok"]) == Path("evil") / "ok"


def test_path_for_layout(tmp_path):
    st = Storage(tmp_path)
    rec = Record(source="arxiv", ext_id="2401.00001", resource_type="paper",
                 categories=["cs", "AI"], file_ext="pdf")
    p = st.path_for(rec)
    assert p == tmp_path / "papers" / "arxiv" / "cs" / "AI" / "2401.00001.pdf"
    ebook = Record(source="gutenberg", ext_id="pg1", resource_type="ebook",
                   categories=["PR"], file_ext="epub")
    assert st.path_for(ebook) == tmp_path / "ebooks" / "gutenberg" / "PR" / "pg1.epub"
    st.close()


def test_mark_and_is_done_resume_semantics(tmp_path):
    st = Storage(tmp_path)
    rec = Record(source="arxiv", ext_id="x1", resource_type="paper", status="metadata")
    st.mark(rec)
    # metadata-only satisfies a metadata-only resume, but NOT a download resume
    assert st.is_done("arxiv", "x1", need_download=False) is True
    assert st.is_done("arxiv", "x1", need_download=True) is False

    rec.status = "downloaded"
    st.mark(rec)
    assert st.is_done("arxiv", "x1", need_download=True) is True
    assert st.is_done("arxiv", "unknown", need_download=False) is False
    st.close()


def test_append_catalog_writes_jsonl(tmp_path):
    st = Storage(tmp_path)
    rec = Record(source="arxiv", ext_id="x1", resource_type="paper", title="t")
    st.append_catalog(rec)
    st.append_catalog(rec)
    lines = (tmp_path / "catalog" / "arxiv.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    st.close()
