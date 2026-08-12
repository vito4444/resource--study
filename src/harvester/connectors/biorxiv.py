"""bioRxiv / medRxiv connector (preprint metadata + fulltext PDF)."""
from __future__ import annotations

from typing import Any, Dict, Iterator

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_API = "https://api.biorxiv.org/details"
_DOMAINS = {"biorxiv": "www.biorxiv.org", "medrxiv": "www.medrxiv.org"}


@register
class BiorxivConnector(BaseConnector):
    name = "biorxiv"
    resource_type = "paper"
    description = "bioRxiv / medRxiv preprints (CC-licensed); fulltext PDF."

    def iter_records(self) -> Iterator[Record]:
        server = str(self.opt("server", "biorxiv")).lower()
        if server not in _DOMAINS:
            server = "biorxiv"
        from_date = self.opt("from_date", "2024-01-01")
        to_date = self.opt("to_date", "2024-12-31")
        cursor = 0
        yielded = 0
        while True:
            url = f"{_API}/{server}/{from_date}/{to_date}/{cursor}"
            data = self.http.get_json(url)
            collection = data.get("collection", [])
            if not collection:
                return
            messages = data.get("messages", [{}])
            total = int(messages[0].get("total", 0)) if messages else 0
            for item in collection:
                yield self._parse(item, server)
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return
            cursor += len(collection)
            if total and cursor >= total:
                return

    def _parse(self, item: Dict[str, Any], server: str) -> Record:
        doi = item.get("doi", "")
        version = str(item.get("version", "1"))
        domain = _DOMAINS[server]
        pdf_url = f"https://{domain}/content/{doi}v{version}.full.pdf"
        authors = [a.strip() for a in str(item.get("authors", "")).split(";") if a.strip()]
        return Record(
            source=self.name,
            ext_id=f"{doi}v{version}",
            resource_type="paper",
            title=item.get("title", ""),
            authors=authors,
            categories=[item.get("category", "preprint")],
            language="en",
            published=item.get("date", ""),
            license=item.get("license", ""),
            landing_url=f"https://{domain}/content/{doi}v{version}",
            download_url=pdf_url,
            file_ext="pdf",
            extra={"doi": doi, "server": item.get("server", server)},
        )
