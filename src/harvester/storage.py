"""On-disk layout, catalog (JSONL) and resumable state (SQLite)."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Iterable, Optional

from .models import Record

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_SEGMENT = 80


def sanitize_segment(value: str, fallback: str = "unknown") -> str:
    """Turn an arbitrary string into a safe single path segment.

    Guarantees no path traversal, no separators, bounded length, non-empty.
    """
    value = (value or "").strip().replace("/", "-").replace("\\", "-")
    value = _UNSAFE.sub("-", value).strip("-._")
    if not value or value in {".", ".."}:
        return fallback
    if len(value) > _MAX_SEGMENT:
        value = value[:_MAX_SEGMENT].rstrip("-._") or fallback
    return value


def category_path(segments: Iterable[str]) -> Path:
    parts = [sanitize_segment(s) for s in segments]
    parts = [p for p in parts if p]
    return Path(*parts) if parts else Path("uncategorized")


class Storage:
    """Filesystem + catalog + state manager rooted at ``base_dir``."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.catalog_dir = self.base_dir / "catalog"
        self.db_path = self.base_dir / "harvest.db"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                source TEXT NOT NULL,
                ext_id TEXT NOT NULL,
                status TEXT NOT NULL,
                category TEXT,
                path TEXT,
                sha256 TEXT,
                bytes INTEGER,
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (source, ext_id)
            )
            """
        )
        self._conn.commit()

    # ---- state ----
    def status_of(self, source: str, ext_id: str) -> Optional[str]:
        cur = self._conn.execute(
            "SELECT status FROM seen WHERE source=? AND ext_id=?", (source, ext_id)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def is_done(self, source: str, ext_id: str, need_download: bool) -> bool:
        """True when this record can be skipped on a resume run."""
        status = self.status_of(source, ext_id)
        if status is None:
            return False
        if need_download:
            return status == "downloaded"
        return status in {"downloaded", "metadata", "skipped"}

    def mark(self, record: Record) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO seen (source, ext_id, status, category, path, sha256, bytes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(source, ext_id) DO UPDATE SET
                    status=excluded.status,
                    category=excluded.category,
                    path=excluded.path,
                    sha256=excluded.sha256,
                    bytes=excluded.bytes,
                    updated_at=datetime('now')
                """,
                (
                    record.source,
                    record.ext_id,
                    record.status,
                    "/".join(record.category_segments()),
                    record.local_path,
                    record.sha256,
                    record.bytes,
                ),
            )
            self._conn.commit()

    def counts_by_status(self) -> Dict[str, int]:
        cur = self._conn.execute("SELECT status, COUNT(*) FROM seen GROUP BY status")
        return {row[0]: row[1] for row in cur.fetchall()}

    def total(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]

    # ---- catalog ----
    def append_catalog(self, record: Record) -> None:
        path = self.catalog_dir / f"{sanitize_segment(record.source)}.jsonl"
        with self._lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(record.to_json() + "\n")

    # ---- paths ----
    def path_for(self, record: Record) -> Path:
        kind = "papers" if record.resource_type == "paper" else "ebooks"
        ext = record.file_ext.lstrip(".") if record.file_ext else "bin"
        filename = f"{sanitize_segment(record.ext_id, fallback='item')}.{ext}"
        return (
            self.base_dir
            / kind
            / sanitize_segment(record.source)
            / category_path(record.category_segments())
            / filename
        )

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
