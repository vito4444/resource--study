"""Minimal monotonic-clock rate limiter (min interval between calls)."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Block so that consecutive ``wait()`` calls are >= ``min_interval`` apart."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()
