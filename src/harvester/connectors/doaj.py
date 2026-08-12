"""DOAJ connector (Directory of Open Access Journals articles)."""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Iterator, List

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_API = "https://doaj.org/api/v2/search/articles"
_PAGE_SIZE = 100


@register
class DoajConnector(BaseConnector):
    name = "doaj"
    resource_type = "paper"
    description = "DOAJ open-access journal articles; PDF when the fulltext link is a direct file."

    def iter_records(self) -> Iterator[Record]:
        query = self.opt("query", "*") or "*"
        encoded = urllib.parse.quote(str(query), safe="")
        page = 1
        yielded = 0
        while True:
            url = f"{_API}/{encoded}"
            data = self.http.get_json(url, params={"page": page, "pageSize": _PAGE_SIZE})
            results = data.get("results", [])
            if not results:
                return
            for item in results:
                yield self._parse(item)
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return
            total = int(data.get("total", 0))
            if page * _PAGE_SIZE >= total:
                return
            page += 1

    def _parse(self, item: Dict[str, Any]) -> Record:
        b = item.get("bibjson", {})
        authors = [a.get("name", "") for a in b.get("author", []) if a.get("name")]
        categories = [s.get("term", "") for s in b.get("subject", []) if s.get("term")]
        journal = b.get("journal", {}) or {}
        languages = journal.get("language") or []
        language = languages[0] if languages else ""

        download_url = ""
        file_ext = ""
        landing = ""
        for link in b.get("link", []):
            url = link.get("url", "")
            if link.get("type") == "fulltext" and url:
                landing = landing or url
                if url.lower().split("?")[0].endswith(".pdf"):
                    download_url = url
                    file_ext = "pdf"

        return Record(
            source=self.name,
            ext_id=str(item.get("id", "")),
            resource_type="paper",
            title=b.get("title", ""),
            authors=authors,
            categories=categories or ["open-access"],
            language=language,
            published=str(b.get("year", "")),
            license="open access (DOAJ)",
            landing_url=landing,
            download_url=download_url,
            file_ext=file_ext,
        )
