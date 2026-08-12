"""Render the GUI offscreen to PNGs for the README / PR (no real display needed).

Run:  QT_QPA_PLATFORM=offscreen python tools/make_screenshots.py
Writes docs/screenshots/*.png
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402

from harvester.gui.app import MainWindow, app_icon  # noqa: E402
from harvester.gui.theme import apply_theme  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"

SAMPLE_LIBRARY = [
    ("arxiv", "paper", "Surgical WAM: A World-Action Model for Data-Efficient Learning", "cs/RO", "downloaded", 1_821_207, "data/papers/arxiv/cs/RO/2608.11204v1.pdf"),
    ("arxiv", "paper", "Attention Is All You Need", "cs/CL", "downloaded", 2_332_182, "data/papers/arxiv/cs/CL/1706.03762v7.pdf"),
    ("openalex", "paper", "Magnetic confinement fusion research review", "Physical-Sciences/Physics-and-Astronomy", "downloaded", 5_018_540, "data/papers/openalex/Physical-Sciences/W3038568908.pdf"),
    ("pmc", "paper", "Genome-wide association study of complex traits", "Nature Genetics", "downloaded", 122_099, "data/papers/pmc/Nature-Genetics/PMC13461269.xml"),
    ("biorxiv", "paper", "KCNQ2/3 regulates efferent slow excitation", "neuroscience", "downloaded", 6_355_727, "data/papers/biorxiv/neuroscience/10.1101-2023.12.30.573731v1.pdf"),
    ("doaj", "paper", "Open-access crystallography structures dataset", "Physics", "metadata", 0, ""),
    ("gutenberg", "ebook", "Pride and Prejudice", "PR", "downloaded", 238_907, "data/ebooks/gutenberg/PR/pg1342.epub"),
    ("gutenberg", "ebook", "The Adventures of Sherlock Holmes", "PR", "downloaded", 2_439_783, "data/ebooks/gutenberg/PR/pg1661.epub"),
    ("internet_archive", "ebook", "Interpreting Schelling: Critical Essays", "Philosophy", "downloaded", 1_441_824, "data/ebooks/internet_archive/Philosophy/schelling.pdf"),
]

SAMPLE_LOG = [
    "16:50:42 INFO harvester: arxiv: downloaded=2",
    "16:50:55 INFO harvester: openalex: downloaded=1, failed=1",
    "16:50:56 INFO harvester: doaj: metadata=2",
    "16:50:58 INFO harvester: pmc: downloaded=2",
    "16:54:57 INFO harvester: biorxiv: downloaded=2",
    "16:54:59 INFO harvester: gutenberg: downloaded=2",
    "16:55:04 INFO harvester: internet_archive: downloaded=2",
    "16:55:04 INFO harvester: run complete — downloaded=11, failed=1, metadata=2",
]


def _populate(w: MainWindow) -> None:
    w.output_edit.setText(str(Path.home() / "study-library"))
    for ev in SAMPLE_LIBRARY:
        w._add_library_row({
            "source": ev[0], "resource_type": ev[1], "title": ev[2], "category": ev[3],
            "status": ev[4], "bytes": ev[5], "local_path": ev[6],
        })
    for line in SAMPLE_LOG:
        w._append_log(line)
    w.progress.setRange(0, 100)
    w.progress.setValue(64)
    w.progress.setFormat("gutenberg…  64 processed")
    w._counts = {"downloaded": 8, "metadata": 2, "skipped": 1}
    w._refresh_counts()


def _shot(app, w: MainWindow, tab: int, name: str) -> None:
    w.tabs.setCurrentIndex(tab)
    app.processEvents()
    OUT.mkdir(parents=True, exist_ok=True)
    w.grab().save(str(OUT / name))
    print("wrote", OUT / name)


def main() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setWindowIcon(app_icon())
    apply_theme(app, dark=False)
    w = MainWindow()
    w.resize(1060, 730)
    w.show()
    _populate(w)
    app.processEvents()

    _shot(app, w, 0, "harvest.png")
    _shot(app, w, 1, "library.png")
    _shot(app, w, 2, "log.png")
    _shot(app, w, 3, "about.png")

    apply_theme(app, dark=True)
    w.dark_act.setChecked(True)
    app.processEvents()
    _shot(app, w, 0, "harvest-dark.png")

    w.close()


if __name__ == "__main__":
    main()
