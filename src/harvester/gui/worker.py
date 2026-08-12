"""Background harvest worker + logging bridge (runs off the GUI thread)."""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from ..config import Config
from ..harvest import Harvester


class HarvestWorker(QObject):
    """Runs a :class:`Harvester` in a worker thread and reports via signals."""

    event = Signal(dict)        # structured progress events from the engine
    finished = Signal(dict)     # totals when the run completes
    failed = Signal(str)        # unexpected error

    def __init__(self, config: Config, only: Optional[List[str]] = None, dry_run: bool = False):
        super().__init__()
        self.config = config
        self.only = only
        self.dry_run = dry_run
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        harvester = Harvester(self.config)
        try:
            totals = harvester.run(
                only=self.only,
                dry_run=self.dry_run,
                show_progress=False,
                on_event=self.event.emit,
                should_stop=self._stop.is_set,
            )
            self.finished.emit(totals)
        except Exception as exc:  # surface, don't crash the GUI thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            harvester.close()


class QtLogBridge(QObject):
    """A logging.Handler adapter that forwards records to a Qt signal."""

    message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.handler = _SignalHandler(self.message)
        self.handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))

    def attach(self, logger_name: str = "harvester", level: int = logging.INFO) -> None:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        if self.handler not in logger.handlers:
            logger.addHandler(self.handler)

    def detach(self, logger_name: str = "harvester") -> None:
        logging.getLogger(logger_name).removeHandler(self.handler)


class _SignalHandler(logging.Handler):
    def __init__(self, signal: Signal) -> None:
        super().__init__()
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._signal.emit(self.format(record))
        except Exception:
            pass
