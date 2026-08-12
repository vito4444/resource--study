"""Project Gutenberg connector (public-domain ebooks via the official catalog)."""
from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path
from typing import Iterator, List, Tuple

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"

# config format name -> (url suffix on /ebooks/<id>, file extension)
_FORMAT_MAP = {
    "epub": (".epub.images", "epub"),
    "epub-noimages": (".epub.noimages", "epub"),
    "txt": (".txt.utf-8", "txt"),
    "html": (".html.images", "html"),
    "kindle": (".kf8.images", "azw3"),
}


@register
class GutenbergConnector(BaseConnector):
    name = "gutenberg"
    resource_type = "ebook"
    description = "Project Gutenberg public-domain ebooks (epub/txt/html), classified by LoC class."

    def _catalog_path(self) -> Path:
        cache = self.config.output_dir / "_cache"
        cache.mkdir(parents=True, exist_ok=True)
        return cache / "pg_catalog.csv.gz"

    def _ensure_catalog(self) -> Path:
        path = self._catalog_path()
        if not path.exists() or path.stat().st_size == 0:
            self.http.download(_CATALOG_URL, path, overwrite=True)
        return path

    def iter_records(self) -> Iterator[Record]:
        languages = [str(x).lower() for x in (self.opt("languages") or [])]
        formats = self._as_list(self.opt("formats") or ["epub", "txt"])
        path = self._ensure_catalog()
        yielded = 0
        with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if (row.get("Type") or "").strip() != "Text":
                    continue
                lang = (row.get("Language") or "").strip().lower()
                if languages and lang not in languages:
                    continue
                rec = self._parse(row, formats)
                if rec is None:
                    continue
                yield rec
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return

    def _download_candidates(self, book_id: str, formats: List[str]) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for fmt in formats:
            entry = _FORMAT_MAP.get(str(fmt).lower())
            if not entry:
                continue
            suffix, ext = entry
            out.append((f"https://www.gutenberg.org/ebooks/{book_id}{suffix}", ext))
        return out

    def _parse(self, row: dict, formats: List[str]) -> Record | None:
        book_id = (row.get("Text#") or "").strip()
        if not book_id:
            return None

        locc = [c.strip() for c in (row.get("LoCC") or "").split(";") if c.strip()]
        shelves = [s.strip() for s in (row.get("Bookshelves") or "").split(";") if s.strip()]
        subjects = [s.strip() for s in (row.get("Subjects") or "").split(";") if s.strip()]
        if locc:
            categories = [locc[0]]
        elif shelves:
            categories = [shelves[0]]
        elif subjects:
            categories = [subjects[0]]
        else:
            categories = ["unclassified"]

        authors = [a.strip() for a in (row.get("Authors") or "").split(";") if a.strip()]
        candidates = self._download_candidates(book_id, formats)
        primary_url, primary_ext = (candidates[0] if candidates else ("", ""))

        return Record(
            source=self.name,
            ext_id=f"pg{book_id}",
            resource_type="ebook",
            title=(row.get("Title") or "").replace("\n", " ").replace("\r", " ").strip(),
            authors=authors,
            categories=categories,
            language=(row.get("Language") or "").strip(),
            published=(row.get("Issued") or "").strip(),
            license="Public domain (Project Gutenberg)",
            landing_url=f"https://www.gutenberg.org/ebooks/{book_id}",
            download_url=primary_url,
            file_ext=primary_ext,
            extra={
                "locc": locc,
                "bookshelves": shelves,
                "subjects": subjects,
                "alt_downloads": candidates[1:],
            },
        )
