"""Offscreen GUI smoke tests. Skipped when PySide6 or a Qt platform is unavailable."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6 import QtWidgets  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    try:
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # no usable Qt platform in this environment
        pytest.skip(f"Qt platform unavailable: {exc}")
    yield app


def test_mainwindow_builds_and_collects_config(qapp, tmp_path):
    from harvester.gui.app import MainWindow

    w = MainWindow()
    try:
        assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == [
            "Harvest", "Library", "Log", "About",
        ]
        assert len(w.source_rows) == 8

        w.output_edit.setText(str(tmp_path))
        w.email_edit.setText("me@example.com")
        w.mode_combo.setCurrentIndex(1)  # metadata only
        for r in w.source_rows:
            r["name_item"].setCheckState(
                Qt.Checked if r["name"] == "arxiv" else Qt.Unchecked
            )
            r["max_spin"].setValue(7)

        cfg = w._collect_config()
        assert cfg.contact_email == "me@example.com"
        assert str(cfg.output_dir) == str(tmp_path)
        assert cfg.download is False
        assert [s.name for s in cfg.enabled_sources()] == ["arxiv"]
        assert cfg.sources["arxiv"].max_records == 7
    finally:
        w.close()


def test_library_row_from_event(qapp):
    from harvester.gui.app import MainWindow

    w = MainWindow()
    try:
        w._add_library_row({
            "source": "gutenberg", "resource_type": "ebook", "title": "Moby Dick",
            "category": "PZ", "status": "downloaded", "bytes": 1048576,
            "local_path": "/tmp/pg2701.epub",
        })
        assert w.library.rowCount() == 1
        assert w.library.item(0, 2).text() == "Moby Dick"
        assert w.library.item(0, 5).text() == "1.0 MB"
    finally:
        w.close()
