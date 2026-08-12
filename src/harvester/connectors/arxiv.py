"""arXiv connector (open-access preprints, PDF)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterator, List

from ..base import BaseConnector
from ..models import Record
from ..registry import register

_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}

# Top-level arXiv categories, used to enumerate "everything" when the config
# leaves `categories` empty. arXiv has no single "all" query, so we sweep the
# taxonomy category by category.
ARXIV_CATEGORIES: List[str] = [
    "cs.AI", "cs.AR", "cs.CC", "cs.CE", "cs.CG", "cs.CL", "cs.CR", "cs.CV",
    "cs.CY", "cs.DB", "cs.DC", "cs.DL", "cs.DM", "cs.DS", "cs.ET", "cs.FL",
    "cs.GL", "cs.GR", "cs.GT", "cs.HC", "cs.IR", "cs.IT", "cs.LG", "cs.LO",
    "cs.MA", "cs.MM", "cs.MS", "cs.NA", "cs.NE", "cs.NI", "cs.OH", "cs.OS",
    "cs.PF", "cs.PL", "cs.RO", "cs.SC", "cs.SD", "cs.SE", "cs.SI", "cs.SY",
    "econ.EM", "econ.GN", "econ.TH",
    "eess.AS", "eess.IV", "eess.SP", "eess.SY",
    "math.AC", "math.AG", "math.AP", "math.AT", "math.CA", "math.CO",
    "math.CT", "math.CV", "math.DG", "math.DS", "math.FA", "math.GM",
    "math.GN", "math.GR", "math.GT", "math.HO", "math.IT", "math.KT",
    "math.LO", "math.MG", "math.MP", "math.NA", "math.NT", "math.OA",
    "math.OC", "math.PR", "math.QA", "math.RA", "math.RT", "math.SG",
    "math.SP", "math.ST",
    "astro-ph.CO", "astro-ph.EP", "astro-ph.GA", "astro-ph.HE",
    "astro-ph.IM", "astro-ph.SR",
    "cond-mat.dis-nn", "cond-mat.mes-hall", "cond-mat.mtrl-sci",
    "cond-mat.other", "cond-mat.quant-gas", "cond-mat.soft",
    "cond-mat.stat-mech", "cond-mat.str-el", "cond-mat.supr-con",
    "gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th", "math-ph",
    "nlin.AO", "nlin.CD", "nlin.CG", "nlin.PS", "nlin.SI",
    "nucl-ex", "nucl-th",
    "physics.acc-ph", "physics.ao-ph", "physics.app-ph", "physics.atm-clus",
    "physics.atom-ph", "physics.bio-ph", "physics.chem-ph", "physics.class-ph",
    "physics.comp-ph", "physics.data-an", "physics.ed-ph", "physics.flu-dyn",
    "physics.gen-ph", "physics.geo-ph", "physics.hist-ph", "physics.ins-det",
    "physics.med-ph", "physics.optics", "physics.plasm-ph", "physics.pop-ph",
    "physics.soc-ph", "physics.space-ph", "quant-ph",
    "q-bio.BM", "q-bio.CB", "q-bio.GN", "q-bio.MN", "q-bio.NC", "q-bio.OT",
    "q-bio.PE", "q-bio.QM", "q-bio.SC", "q-bio.TO",
    "q-fin.CP", "q-fin.EC", "q-fin.GN", "q-fin.MF", "q-fin.PM", "q-fin.PR",
    "q-fin.RM", "q-fin.ST", "q-fin.TR",
    "stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH",
]

_API = "https://export.arxiv.org/api/query"
_PAGE = 100


@register
class ArxivConnector(BaseConnector):
    name = "arxiv"
    resource_type = "paper"
    description = "arXiv open-access preprints (physics, CS, math, stats, ...), PDF."

    def iter_records(self) -> Iterator[Record]:
        cats = self.opt("categories") or ARXIV_CATEGORIES
        cats = self._as_list(cats)
        yielded = 0
        for cat in cats:
            for rec in self._iter_category(cat):
                yield rec
                yielded += 1
                if self.max_records and yielded >= self.max_records:
                    return

    def _iter_category(self, category: str) -> Iterator[Record]:
        start = 0
        while True:
            params = {
                "search_query": f"cat:{category}",
                "start": start,
                "max_results": _PAGE,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            text = self.http.get_text(_API, params=params)
            root = ET.fromstring(text)
            entries = root.findall("a:entry", _NS)
            if not entries:
                return
            for entry in entries:
                rec = self._parse_entry(entry)
                if rec is not None:
                    yield rec
            if len(entries) < _PAGE:
                return
            start += _PAGE
            # arXiv's index caps deep paging; stop defensively.
            if start >= 30000:
                return

    def _parse_entry(self, entry: ET.Element) -> Record | None:
        id_el = entry.find("a:id", _NS)
        if id_el is None or not id_el.text:
            return None
        arxiv_id = id_el.text.rstrip("/").split("/abs/")[-1]
        title_el = entry.find("a:title", _NS)
        title = (title_el.text or "").strip() if title_el is not None else ""
        summary_el = entry.find("a:summary", _NS)
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        authors = [
            (n.text or "").strip()
            for n in entry.findall("a:author/a:name", _NS)
            if n.text
        ]
        published_el = entry.find("a:published", _NS)
        published = (published_el.text or "")[:10] if published_el is not None else ""
        primary_el = entry.find("arxiv:primary_category", _NS)
        primary = primary_el.get("term") if primary_el is not None else ""
        all_cats = [c.get("term") for c in entry.findall("a:category", _NS) if c.get("term")]

        pdf_url = ""
        for link in entry.findall("a:link", _NS):
            if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
                break
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        segments = primary.split(".") if primary else ["misc"]
        return Record(
            source=self.name,
            ext_id=arxiv_id,
            resource_type="paper",
            title=title,
            authors=authors,
            categories=segments,
            language="en",
            published=published,
            license="arXiv (author license / arXiv.org perpetual)",
            landing_url=id_el.text,
            download_url=pdf_url,
            file_ext="pdf",
            description=summary,
            extra={"primary_category": primary, "all_categories": all_cats},
        )
