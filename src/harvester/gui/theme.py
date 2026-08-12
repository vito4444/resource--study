"""A clean, restrained visual theme (Fusion + optional dark palette)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

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
QPushButton:default { font-weight: 600; }
QTabBar::tab { padding: 8px 16px; }
QLineEdit, QComboBox, QSpinBox { padding: 4px 6px; border-radius: 6px; }
QProgressBar { border-radius: 6px; height: 20px; text-align: center; }
QTableWidget { gridline-color: palette(midlight); }
"""


def _dark_palette() -> QPalette:
    p = QPalette()
    bg = QColor(32, 34, 37)
    base = QColor(24, 26, 28)
    text = QColor(222, 224, 228)
    highlight = QColor(45, 108, 223)
    p.setColor(QPalette.Window, bg)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, bg)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, bg)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor(255, 90, 90))
    p.setColor(QPalette.Link, highlight)
    p.setColor(QPalette.Highlight, highlight)
    p.setColor(QPalette.HighlightedText, Qt.white)
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 122, 126))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 122, 126))
    return p


def apply_theme(app, dark: bool = False) -> None:
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    app.setPalette(_dark_palette() if dark else app.style().standardPalette())
    app.setStyleSheet(_STYLESHEET)
