"""Internet Archive connector (public-domain texts)."""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_SEARCH = "https://archive.org/advancedsearch.php"
_METADATA = "https://archive.org/metadata"
_DOWNLOAD = "https://archive.org/download"
_ROWS = 100

_FORMAT_EXT = {
    "Text PDF": "pdf",
    "Grayscale PDF": "pdf",
    "Image Container PDF": "pdf",
    "EPUB": "epub",
    "DjVuTXT": "txt",
    "Abbyy GZ": "gz",
    "Full Text": "txt",
}


@register
class InternetArchiveConnector(BaseConnector):
    name = "internet_archive"
    resource_type = "ebook"
    description = "Internet Archive public-domain texts (PDF/EPUB/TXT)."

    def iter_records(self) -> Iterator[Record]:
        query = self.opt(
            "query",
            'mediatype:texts AND possible-copyright-status:"NOT_IN_COPYRIGHT"',
        )
        formats = self._as_list(self.opt("formats") or ["Text PDF", "EPUB", "DjVuTXT"])
        want_download = self.config.download and self.cfg.download
        page = 1
        yielded = 0
        while True:
            params = [
                ("q", query),
                ("rows", _ROWS),
                ("page", page),
                ("output", "json"),
            ]
            for field in ("identifier", "title", "creator", "subject", "year", "language", "licenseurl"):
                params.append(("fl[]", field))
            data = self.http.get_json(_SEARCH, params=params)
            response = data.get("response", {})
            docs = response.get("docs", [])
            if not docs:
                return
            for doc in docs:
                rec = self._parse(doc, formats, want_download)
                if rec is not None:
                    yield rec
                    yielded += 1
                    if self.max_records and yielded >= self.max_records:
                        return
            num_found = int(response.get("numFound", 0))
            if page * _ROWS >= num_found:
                return
            page += 1

    def _pick_files(self, identifier: str, formats: List[str]) -> List[Tuple[str, str]]:
        try:
            meta = self.http.get_json(f"{_METADATA}/{identifier}")
        except Exception:
            return []
        files = meta.get("files", [])
        by_format: Dict[str, str] = {}
        for f in files:
            fmt = f.get("format")
            name = f.get("name")
            if fmt and name and fmt not in by_format:
                by_format[fmt] = name
        out: List[Tuple[str, str]] = []
        for fmt in formats:
            if fmt in by_format:
                ext = _FORMAT_EXT.get(fmt, "bin")
                out.append((f"{_DOWNLOAD}/{identifier}/{by_format[fmt]}", ext))
        return out

    def _parse(self, doc: Dict[str, Any], formats: List[str], want_download: bool) -> Record | None:
        identifier = doc.get("identifier")
        if not identifier:
            return None
        subjects = self._as_list(doc.get("subject")) or ["texts"]
        authors = self._as_list(doc.get("creator"))
        languages = self._as_list(doc.get("language"))

        candidates: List[Tuple[str, str]] = []
        if want_download:
            candidates = self._pick_files(identifier, formats)
        primary_url, primary_ext = (candidates[0] if candidates else ("", ""))

        return Record(
            source=self.name,
            ext_id=identifier,
            resource_type="ebook",
            title=str(doc.get("title", "")),
            authors=authors,
            categories=subjects[:1],
            language=languages[0] if languages else "",
            published=str(doc.get("year", "")),
            license=str(doc.get("licenseurl", "")),
            landing_url=f"https://archive.org/details/{identifier}",
            download_url=primary_url,
            file_ext=primary_ext,
            extra={"subjects": subjects, "alt_downloads": candidates[1:]},
        )
