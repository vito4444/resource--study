"""Crossref connector (scholarly metadata index; no fulltext)."""
from __future__ import annotations

from typing import Any, Dict, Iterator, List

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_API = "https://api.crossref.org/works"
_ROWS = 100


@register
class CrossrefConnector(BaseConnector):
    name = "crossref"
    resource_type = "paper"
    description = "Crossref metadata index (all DOIs); metadata only, no fulltext download."

    def iter_records(self) -> Iterator[Record]:
        cursor = "*"
        query = self.opt("query", "") or ""
        yielded = 0
        while cursor:
            params: Dict[str, Any] = {
                "rows": _ROWS,
                "cursor": cursor,
                "mailto": self.config.contact_email,
            }
            if query:
                params["query"] = query
            data = self.http.get_json(_API, params=params)
            message = data.get("message", {})
            items = message.get("items", [])
            if not items:
                return
            for item in items:
                yield self._parse(item)
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return
            cursor = message.get("next-cursor")

    def _parse(self, item: Dict[str, Any]) -> Record:
        titles = item.get("title") or [""]
        authors = [
            " ".join(x for x in [a.get("given"), a.get("family")] if x)
            for a in item.get("author", [])
        ]
        authors = [a for a in authors if a]
        subjects: List[str] = item.get("subject") or []
        year = ""
        issued = (item.get("issued") or {}).get("date-parts") or [[None]]
        if issued and issued[0] and issued[0][0]:
            year = str(issued[0][0])
        licenses = item.get("license") or []
        license_url = licenses[0].get("URL", "") if licenses else ""
        container = item.get("container-title") or [""]

        return Record(
            source=self.name,
            ext_id=item.get("DOI", ""),
            resource_type="paper",
            title=titles[0] if titles else "",
            authors=authors,
            categories=subjects or [item.get("type", "work")],
            language="",
            published=year,
            license=license_url,
            landing_url=item.get("URL", ""),
            download_url="",
            file_ext="",
            extra={"doi": item.get("DOI", ""), "container": container[0] if container else ""},
        )
