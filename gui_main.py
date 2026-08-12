"""PyInstaller entry point for the desktop GUI.

Kept at the repo root so the packaging spec has a stable script to freeze.
"""
from harvester.gui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
