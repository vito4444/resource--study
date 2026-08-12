"""PubMed Central Open Access connector (fulltext JATS XML via E-utilities)."""
from __future__ import annotations

from typing import Any, Dict, Iterator, List

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_BATCH = 100


@register
class PmcConnector(BaseConnector):
    name = "pmc"
    resource_type = "paper"
    description = "PubMed Central Open Access subset; fulltext downloaded as JATS XML."

    def _eutils_common(self) -> Dict[str, str]:
        return {"tool": "resource-study-harvester", "email": self.config.contact_email}

    def iter_records(self) -> Iterator[Record]:
        query = self.opt("query", "open access[filter]") or "open access[filter]"
        retstart = 0
        yielded = 0
        while True:
            params = dict(self._eutils_common())
            params.update({
                "db": "pmc",
                "term": query,
                "retmode": "json",
                "retmax": _BATCH,
                "retstart": retstart,
            })
            data = self.http.get_json(_ESEARCH, params=params)
            idlist = (data.get("esearchresult") or {}).get("idlist", [])
            if not idlist:
                return
            for rec in self._records_for_ids(idlist):
                yield rec
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return
            retstart += _BATCH

    def _records_for_ids(self, idlist: List[str]) -> Iterator[Record]:
        params = dict(self._eutils_common())
        params.update({"db": "pmc", "id": ",".join(idlist), "retmode": "json"})
        summary = self.http.get_json(_ESUMMARY, params=params)
        result = summary.get("result", {})
        for uid in result.get("uids", []):
            item = result.get(uid, {})
            yield self._parse(uid, item)

    def _parse(self, uid: str, item: Dict[str, Any]) -> Record:
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        journal = item.get("fulljournalname") or item.get("source") or "PMC"
        sortdate = (item.get("sortdate") or "")[:10].replace("/", "-")

        doi = ""
        for aid in item.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")

        download_url = (
            f"{_EFETCH}?db=pmc&id={uid}"
            f"&tool=resource-study-harvester&email={self.config.contact_email}"
        )
        return Record(
            source=self.name,
            ext_id=f"PMC{uid}",
            resource_type="paper",
            title=item.get("title", ""),
            authors=authors,
            categories=[journal],
            language="",
            published=sortdate,
            license="PMC Open Access subset",
            landing_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{uid}/",
            download_url=download_url,
            file_ext="xml",
            extra={"doi": doi, "journal": journal},
        )
