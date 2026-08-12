"""OpenAlex connector (scholarly works metadata + OA PDF when available)."""
from __future__ import annotations

from typing import Any, Dict, Iterator, List

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_API = "https://api.openalex.org/works"
_PER_PAGE = 200


@register
class OpenAlexConnector(BaseConnector):
    name = "openalex"
    resource_type = "paper"
    description = "OpenAlex scholarly works; metadata for all, PDF where an open-access copy exists."

    def _build_filter(self) -> str:
        parts: List[str] = []
        if self.opt("only_open_access", True):
            parts.append("is_oa:true")
        for key, value in (self.opt("filters") or {}).items():
            parts.append(f"{key}:{value}")
        return ",".join(parts)

    def iter_records(self) -> Iterator[Record]:
        cursor = "*"
        filter_str = self._build_filter()
        yielded = 0
        while cursor:
            params: Dict[str, Any] = {
                "per-page": _PER_PAGE,
                "cursor": cursor,
                "mailto": self.config.contact_email,
            }
            if filter_str:
                params["filter"] = filter_str
            data = self.http.get_json(_API, params=params)
            results = data.get("results", [])
            if not results:
                return
            for work in results:
                yield self._parse(work)
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return
            cursor = (data.get("meta") or {}).get("next_cursor")

    def _parse(self, work: Dict[str, Any]) -> Record:
        ext_id = str(work.get("id", "")).rstrip("/").split("/")[-1]
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in work.get("authorships", [])
        ]
        authors = [a for a in authors if a]

        categories: List[str] = []
        topic = work.get("primary_topic") or {}
        for level in ("domain", "field", "subfield"):
            node = topic.get(level) or {}
            name = node.get("display_name")
            if name:
                categories.append(name)
        if not categories:
            categories = [work.get("type") or "work"]

        best = work.get("best_oa_location") or {}
        oa = work.get("open_access") or {}
        pdf_url = best.get("pdf_url") or ""

        return Record(
            source=self.name,
            ext_id=ext_id,
            resource_type="paper",
            title=work.get("title") or work.get("display_name") or "",
            authors=authors,
            categories=categories,
            language=work.get("language") or "",
            published=work.get("publication_date") or "",
            license=best.get("license") or oa.get("oa_status") or "",
            landing_url=(work.get("ids") or {}).get("doi") or work.get("id") or "",
            download_url=pdf_url,
            file_ext="pdf" if pdf_url else "",
            extra={"doi": (work.get("ids") or {}).get("doi", ""), "is_oa": oa.get("is_oa")},
        )
