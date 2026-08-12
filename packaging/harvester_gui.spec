# PyInstaller spec for the Resource Study Harvester desktop GUI.
# Build (on the target OS — PyInstaller does not cross-compile):
#   pip install .[build]
#   pyinstaller --noconfirm --clean packaging/harvester_gui.spec
# Produces a single-file executable in dist/.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH injected by PyInstaller)

entry = os.path.join(ROOT, "gui_main.py")

# Bundle package data (resources/default_config.yaml) and make sure every
# connector + gui submodule is collected even though they are imported lazily.
datas = collect_data_files("harvester")
hiddenimports = (
    collect_submodules("harvester.connectors")
    + collect_submodules("harvester.gui")
)

icon_path = os.path.join(ROOT, "packaging", "icon.ico")
icon = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [entry],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ResourceStudyHarvester",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # GUI app: no console window
    disable_windowed_traceback=False,
    icon=icon,
)
