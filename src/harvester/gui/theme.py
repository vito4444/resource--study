"""A clean, restrained visual theme (Fusion + light spacing tweaks)."""
from __future__ import annotations

_STYLESHEET = """
QMainWindow, QWidget { font-size: 13px; }
QGroupBox {
    border: 1px solid palette(mid);
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: palette(highlight);
    font-weight: 600;
}
QPushButton {
    padding: 6px 14px;
    border-radius: 6px;
}
QTabBar::tab { padding: 8px 16px; }
QLineEdit, QComboBox, QSpinBox { padding: 4px 6px; border-radius: 6px; }
QProgressBar { border-radius: 6px; height: 20px; text-align: center; }
QTableWidget { gridline-color: palette(midlight); }
"""


def apply_theme(app) -> None:
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    app.setStyleSheet(_STYLESHEET)
