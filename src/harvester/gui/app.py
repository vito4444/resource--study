"""Main window for the resource-study-harvester desktop app."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import Config, load_default_config
from ..registry import available
from ..storage import Storage
from .theme import apply_theme
from .worker import HarvestWorker, QtLogBridge

APP_NAME = "Resource Study Harvester"


def _human_size(n: int) -> str:
    size = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.resize(1040, 720)

        self._base_config: Config = load_default_config()
        self._descriptions = {name: cls.description for name, cls in available().items()}
        self._types = {name: cls.resource_type for name, cls in available().items()}
        self.source_rows: List[dict] = []

        self._thread: Optional[QThread] = None
        self._worker: Optional[HarvestWorker] = None
        self._running = False

        self.log_bridge = QtLogBridge()
        self.log_bridge.message.connect(self._append_log)
        self.log_bridge.attach()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_harvest_tab(), "Harvest")
        self.tabs.addTab(self._build_library_tab(), "Library")
        self.tabs.addTab(self._build_log_tab(), "Log")
        self.tabs.addTab(self._build_about_tab(), "About")

        self._build_menu()
        self.statusBar().showMessage("Ready")

    # ---------------- Harvest tab ----------------
    def _build_harvest_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_settings_group())
        root.addWidget(self._build_sources_group(), stretch=1)
        root.addWidget(self._build_controls_group())
        return page

    def _build_settings_group(self) -> QGroupBox:
        box = QGroupBox("Settings")
        grid = QGridLayout(box)
        grid.setColumnStretch(1, 1)

        self.output_edit = QLineEdit(str(Path(self._base_config.output_dir).resolve()))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_output_dir)
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit)
        out_row.addWidget(browse)
        grid.addWidget(QLabel("Output folder"), 0, 0)
        grid.addLayout(out_row, 0, 1, 1, 3)

        self.email_edit = QLineEdit(self._base_config.contact_email)
        self.email_edit.setPlaceholderText("you@example.com (sent to polite-pool APIs)")
        grid.addWidget(QLabel("Contact email"), 1, 0)
        grid.addWidget(self.email_edit, 1, 1)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Download files", "Metadata only"])
        grid.addWidget(QLabel("Mode"), 1, 2)
        grid.addWidget(self.mode_combo, 1, 3)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 100_000_000)
        self.max_spin.setValue(50)
        self.max_spin.setSpecialValueText("unlimited (0)")
        self.max_spin.setToolTip("Applied to every source when you press 'Set all'. 0 = unlimited.")
        set_all = QPushButton("Set all")
        set_all.clicked.connect(self._apply_max_to_all)
        max_row = QHBoxLayout()
        max_row.addWidget(self.max_spin)
        max_row.addWidget(set_all)
        grid.addWidget(QLabel("Per-source limit"), 2, 0)
        grid.addLayout(max_row, 2, 1)

        self.overwrite_check = QCheckBox("Re-download existing files (overwrite)")
        self.overwrite_check.setChecked(self._base_config.overwrite)
        grid.addWidget(self.overwrite_check, 2, 2, 1, 2)

        return box

    def _build_sources_group(self) -> QGroupBox:
        box = QGroupBox("Sources  (only legally open content is fetched)")
        layout = QVBoxLayout(box)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Source", "Type", "Max (0 = all)", "What it harvests"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        for name in sorted(self._base_config.sources):
            src = self._base_config.sources[name]
            row = table.rowCount()
            table.insertRow(row)

            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            name_item.setCheckState(Qt.Checked if src.enabled else Qt.Unchecked)
            f = QFont()
            f.setBold(True)
            name_item.setFont(f)
            table.setItem(row, 0, name_item)

            table.setItem(row, 1, QTableWidgetItem(self._types.get(name, "")))

            spin = QSpinBox()
            spin.setRange(0, 100_000_000)
            spin.setValue(int(src.max_records))
            spin.setSpecialValueText("all (0)")
            table.setCellWidget(row, 2, spin)

            table.setItem(row, 3, QTableWidgetItem(self._descriptions.get(name, "")))

            self.source_rows.append({"name": name, "name_item": name_item, "max_spin": spin})

        table.resizeColumnsToContents()
        self.sources_table = table
        layout.addWidget(table)

        hint = QLabel(
            "Tip: leave limits small for a quick first run; set a source's Max to 0 to "
            "harvest it exhaustively (can be very large)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(hint)
        return box

    def _build_controls_group(self) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("Start harvest")
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(lambda: self._start(dry_run=False))
        self.dry_btn = QPushButton("Dry run")
        self.dry_btn.clicked.connect(lambda: self._start(dry_run=True))
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.open_btn = QPushButton("Open output folder")
        self.open_btn.clicked.connect(self._open_output_dir)

        for b in (self.start_btn, self.dry_btn, self.stop_btn):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.open_btn)
        v.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Idle")
        v.addWidget(self.progress)

        self.counts_label = QLabel("")
        self.counts_label.setStyleSheet("color: palette(mid);")
        v.addWidget(self.counts_label)

        self._counts: Dict[str, int] = {}
        return wrap

    # ---------------- Library tab ----------------
    def _build_library_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 14)

        bar = QHBoxLayout()
        reload_btn = QPushButton("Reload from catalog")
        reload_btn.clicked.connect(self._reload_library)
        open_sel = QPushButton("Open selected file")
        open_sel.clicked.connect(self._open_selected_library)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by title / source / category…")
        self.filter_edit.textChanged.connect(self._apply_library_filter)
        bar.addWidget(reload_btn)
        bar.addWidget(open_sel)
        bar.addWidget(self.filter_edit, stretch=1)
        v.addLayout(bar)

        self.library = QTableWidget(0, 7)
        self.library.setHorizontalHeaderLabels(
            ["Source", "Type", "Title", "Category", "Status", "Size", "Path"]
        )
        self.library.verticalHeader().setVisible(False)
        self.library.setEditTriggers(QTableWidget.NoEditTriggers)
        self.library.setSelectionBehavior(QTableWidget.SelectRows)
        self.library.setSortingEnabled(True)
        self.library.doubleClicked.connect(self._open_selected_library)
        h = self.library.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(6, QHeaderView.Stretch)
        v.addWidget(self.library)
        return page

    # ---------------- Log tab ----------------
    def _build_log_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 14)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setFont(QFont("monospace"))
        v.addWidget(self.log_view)
        clear = QPushButton("Clear log")
        clear.clicked.connect(self.log_view.clear)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(clear)
        v.addLayout(row)
        return page

    # ---------------- About tab ----------------
    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 14)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        rows = "".join(
            f"<tr><td><b>{n}</b></td><td>{self._types.get(n,'')}</td><td>{self._descriptions.get(n,'')}</td></tr>"
            for n in sorted(self._descriptions)
        )
        browser.setHtml(
            f"""
            <h2>{APP_NAME}</h2>
            <p>Version {__version__}. A categorized downloader for <b>legally open</b>
            study resources: open-access scholarly papers and public-domain /
            freely-licensed ebooks.</p>
            <p><b>Scope.</b> Only content that is explicitly free to download is
            fetched. Paywalled or access-restricted material is never retrieved,
            and shadow libraries are out of scope by design. Downloaded items keep
            their own license, recorded in the catalog — review it before
            redistributing.</p>
            <h3>Sources</h3>
            <table cellpadding="6" cellspacing="0" border="0">
              <tr><th align="left">Source</th><th align="left">Type</th><th align="left">Harvests</th></tr>
              {rows}
            </table>
            <p style="margin-top:14px">Project:
            <a href="https://github.com/vito4444/resource--study">github.com/vito4444/resource--study</a></p>
            """
        )
        v.addWidget(browser)
        return page

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_out = QAction("Open output folder", self)
        open_out.triggered.connect(self._open_output_dir)
        file_menu.addAction(open_out)
        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

    # ---------------- config assembly ----------------
    def _collect_config(self) -> Config:
        cfg = load_default_config()
        cfg.output_dir = Path(self.output_edit.text().strip() or "data")
        cfg.contact_email = self.email_edit.text().strip() or "anonymous@example.com"
        cfg.download = self.mode_combo.currentIndex() == 0
        cfg.overwrite = self.overwrite_check.isChecked()
        enabled_map = {r["name"]: (r["name_item"].checkState() == Qt.Checked) for r in self.source_rows}
        max_map = {r["name"]: r["max_spin"].value() for r in self.source_rows}
        for name, src in cfg.sources.items():
            if name in enabled_map:
                src.enabled = enabled_map[name]
                src.max_records = max_map[name]
                src.download = cfg.download
        return cfg

    # ---------------- run lifecycle ----------------
    def _start(self, dry_run: bool) -> None:
        if self._running:
            return
        cfg = self._collect_config()
        if not cfg.enabled_sources():
            QMessageBox.warning(self, APP_NAME, "Enable at least one source (tick it in the table).")
            return
        Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)

        self._counts = {}
        self._processed_total = 0
        self.counts_label.setText("")
        self.progress.setRange(0, 0)  # busy indicator
        self.progress.setFormat("Starting…")
        self._set_running(True)

        self._thread = QThread(self)
        self._worker = HarvestWorker(cfg, dry_run=dry_run)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event.connect(self._on_event)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _stop(self) -> None:
        if self._worker:
            self._worker.stop()
            self.statusBar().showMessage("Stopping after the current item…")
            self.stop_btn.setEnabled(False)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.start_btn.setEnabled(not running)
        self.dry_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _teardown_thread(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None

    # ---------------- event handling (GUI thread) ----------------
    def _on_event(self, ev: dict) -> None:
        etype = ev.get("type")
        if etype == "source_start":
            self.progress.setFormat(f"{ev.get('source')}…  %v processed")
            self.statusBar().showMessage(f"Harvesting {ev.get('source')}")
        elif etype == "record":
            self._processed_total += 1
            self.progress.setValue(self._processed_total)
            status = ev.get("status", "")
            self._counts[status] = self._counts.get(status, 0) + 1
            self._refresh_counts()
            if status in ("downloaded", "metadata", "preview"):
                self._add_library_row(ev)
        elif etype == "source_done":
            self.statusBar().showMessage(f"Finished {ev.get('source')}")

    def _refresh_counts(self) -> None:
        parts = [f"{k}: {v}" for k, v in sorted(self._counts.items())]
        self.counts_label.setText("   ".join(parts))

    def _on_finished(self, totals: dict) -> None:
        self._teardown_thread()
        self._set_running(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        summary = ", ".join(f"{k}={v}" for k, v in sorted(totals.items())) or "nothing"
        self.progress.setFormat(f"Done — {summary}")
        self.statusBar().showMessage(f"Done — {summary}")

    def _on_failed(self, message: str) -> None:
        self._teardown_thread()
        self._set_running(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Failed")
        QMessageBox.critical(self, APP_NAME, f"Harvest failed:\n{message}")

    # ---------------- library ----------------
    def _add_library_row(self, ev: dict) -> None:
        t = self.library
        t.setSortingEnabled(False)
        row = t.rowCount()
        t.insertRow(row)
        size_item = QTableWidgetItem(_human_size(ev.get("bytes", 0)))
        size_item.setData(Qt.UserRole, int(ev.get("bytes", 0)))
        values = [
            ev.get("source", ""),
            ev.get("resource_type", ""),
            ev.get("title", ""),
            ev.get("category", ""),
            ev.get("status", ""),
        ]
        for col, val in enumerate(values):
            t.setItem(row, col, QTableWidgetItem(str(val)))
        t.setItem(row, 5, size_item)
        t.setItem(row, 6, QTableWidgetItem(ev.get("local_path", "")))
        t.setSortingEnabled(True)
        self._apply_library_filter(self.filter_edit.text())

    def _reload_library(self) -> None:
        out = Path(self.output_edit.text().strip() or "data")
        catalog_dir = out / "catalog"
        self.library.setRowCount(0)
        if not catalog_dir.exists():
            self.statusBar().showMessage(f"No catalog under {catalog_dir}")
            return
        count = 0
        for jsonl in sorted(catalog_dir.glob("*.jsonl")):
            with jsonl.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._add_library_row({
                        "source": rec.get("source", ""),
                        "resource_type": rec.get("resource_type", ""),
                        "title": rec.get("title", ""),
                        "category": "/".join(rec.get("categories", []) or []),
                        "status": rec.get("status", ""),
                        "bytes": rec.get("bytes", 0),
                        "local_path": rec.get("local_path", ""),
                    })
                    count += 1
        self.statusBar().showMessage(f"Loaded {count} catalog records from {catalog_dir}")

    def _apply_library_filter(self, text: str) -> None:
        text = (text or "").lower()
        for row in range(self.library.rowCount()):
            hay = " ".join(
                (self.library.item(row, c).text() if self.library.item(row, c) else "")
                for c in (0, 2, 3)
            ).lower()
            self.library.setRowHidden(row, text not in hay)

    def _open_selected_library(self, *_args) -> None:
        row = self.library.currentRow()
        if row < 0:
            return
        path_item = self.library.item(row, 6)
        if path_item and path_item.text():
            self._open_path(path_item.text())

    # ---------------- misc actions ----------------
    def _pick_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text())
        if chosen:
            self.output_edit.setText(chosen)

    def _apply_max_to_all(self) -> None:
        value = self.max_spin.value()
        for r in self.source_rows:
            r["max_spin"].setValue(value)

    def _open_output_dir(self) -> None:
        self._open_path(self.output_edit.text().strip() or "data")

    def _open_path(self, path: str) -> None:
        p = Path(path)
        target = p if p.exists() else p.parent
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))
        else:
            self.statusBar().showMessage(f"Path does not exist yet: {target}")

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._worker:
            self._worker.stop()
        self._teardown_thread()
        self.log_bridge.detach()
        super().closeEvent(event)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
