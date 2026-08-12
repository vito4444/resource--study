from __future__ import annotations

from conftest import FakeHttp, make_config, make_source

from harvester.connectors.arxiv import ArxivConnector
from harvester.connectors.biorxiv import BiorxivConnector
from harvester.connectors.crossref import CrossrefConnector
from harvester.connectors.doaj import DoajConnector
from harvester.connectors.gutenberg import GutenbergConnector
from harvester.connectors.internet_archive import InternetArchiveConnector
from harvester.connectors.openalex import OpenAlexConnector
from harvester.connectors.pmc import PmcConnector

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>A Great Paper</title>
    <summary>We prove things.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <arxiv:primary_category term="cs.AI"/>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
    <link title="pdf" type="application/pdf" href="http://arxiv.org/pdf/2401.01234v1"/>
  </entry>
</feed>"""


def test_arxiv_parse(tmp_path):
    c = ArxivConnector(make_source("arxiv", categories=["cs.AI"], max_records=10),
                       make_config(tmp_path), FakeHttp(text_seq=[ARXIV_ATOM]))
    recs = list(c.iter_records())
    assert len(recs) == 1
    r = recs[0]
    assert r.ext_id == "2401.01234v1"
    assert r.title == "A Great Paper"
    assert r.authors == ["Ada Lovelace", "Alan Turing"]
    assert r.categories == ["cs", "AI"]          # primary_category split -> tree
    assert r.download_url.endswith("2401.01234v1")
    assert r.file_ext == "pdf"


def test_openalex_parse(tmp_path):
    work = {
        "id": "https://openalex.org/W42", "display_name": "OA Work",
        "publication_date": "2023-05-01", "language": "en",
        "authorships": [{"author": {"display_name": "Grace Hopper"}}],
        "primary_topic": {
            "domain": {"display_name": "Physical Sciences"},
            "field": {"display_name": "Computer Science"},
            "subfield": {"display_name": "Artificial Intelligence"},
        },
        "best_oa_location": {"pdf_url": "https://example.org/paper.pdf", "license": "cc-by"},
        "open_access": {"is_oa": True, "oa_url": "https://example.org/paper.pdf"},
        "ids": {"doi": "https://doi.org/10.1/abc"},
    }
    http = FakeHttp(json_seq=[{"results": [work], "meta": {"next_cursor": "next"}}, {"results": []}])
    c = OpenAlexConnector(make_source("openalex", max_records=1), make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.ext_id == "W42"
    assert r.categories == ["Physical Sciences", "Computer Science", "Artificial Intelligence"]
    assert r.download_url == "https://example.org/paper.pdf"
    assert r.file_ext == "pdf"


def test_doaj_parse_landing_is_metadata_only(tmp_path):
    item = {"id": "doaj-1", "bibjson": {
        "title": "OA Article", "year": "2022",
        "author": [{"name": "N. Bourbaki"}],
        "subject": [{"term": "Physics"}],
        "journal": {"language": ["en"]},
        "link": [{"type": "fulltext", "url": "https://doi.org/10.1/landing"}],
    }}
    http = FakeHttp(json_seq=[{"results": [item], "total": 1, "page": 1, "pageSize": 100}])
    c = DoajConnector(make_source("doaj", query="*", max_records=1), make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.categories == ["Physics"]
    assert r.download_url == ""          # landing page, not a direct pdf -> metadata only
    assert r.landing_url.endswith("landing")


def test_doaj_parse_direct_pdf(tmp_path):
    item = {"id": "doaj-2", "bibjson": {
        "title": "OA Article 2",
        "link": [{"type": "fulltext", "url": "https://example.org/x.pdf"}],
    }}
    http = FakeHttp(json_seq=[{"results": [item], "total": 1}])
    c = DoajConnector(make_source("doaj", max_records=1), make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.download_url == "https://example.org/x.pdf"
    assert r.file_ext == "pdf"


def test_pmc_parse_uses_efetch(tmp_path):
    esearch = {"esearchresult": {"idlist": ["555"]}}
    esummary = {"result": {"uids": ["555"], "555": {
        "title": "Bio Paper", "fulljournalname": "Journal of Tests",
        "sortdate": "2020/03/04 00:00",
        "authors": [{"name": "R. Franklin"}],
        "articleids": [{"idtype": "doi", "value": "10.1/xyz"}],
    }}}
    http = FakeHttp(json_seq=[esearch, esummary])
    c = PmcConnector(make_source("pmc", max_records=1), make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.ext_id == "PMC555"
    assert r.categories == ["Journal of Tests"]
    assert r.published == "2020-03-04"
    assert "efetch.fcgi" in r.download_url and "id=555" in r.download_url
    assert r.file_ext == "xml"


def test_biorxiv_parse(tmp_path):
    coll = {"collection": [{
        "doi": "10.1101/2024.01.01.111", "title": "Pre Print", "version": "2",
        "authors": "Smith, J.; Doe, A.", "category": "neuroscience",
        "date": "2024-01-01", "license": "cc_by", "server": "bioRxiv",
    }], "messages": [{"total": "1"}]}
    http = FakeHttp(json_seq=[coll])
    c = BiorxivConnector(make_source("biorxiv", server="biorxiv", max_records=1),
                         make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.ext_id == "10.1101/2024.01.01.111v2"
    assert r.categories == ["neuroscience"]
    assert r.download_url == "https://www.biorxiv.org/content/10.1101/2024.01.01.111v2.full.pdf"
    assert r.authors == ["Smith, J.", "Doe, A."]


def test_crossref_metadata_only(tmp_path):
    resp = {"message": {"items": [{
        "DOI": "10.1/aaa", "title": ["Indexed Work"],
        "author": [{"given": "Iso", "family": "Standard"}],
        "issued": {"date-parts": [[2019]]},
        "subject": ["Computer Science"], "type": "journal-article",
        "URL": "https://doi.org/10.1/aaa",
    }], "next-cursor": "c2"}}
    http = FakeHttp(json_seq=[resp, {"message": {"items": []}}])
    c = CrossrefConnector(make_source("crossref", max_records=1), make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.ext_id == "10.1/aaa"
    assert r.categories == ["Computer Science"]
    assert r.download_url == ""
    assert r.authors == ["Iso Standard"]


def test_gutenberg_parse_prefers_locc_and_builds_download(tmp_path):
    c = GutenbergConnector(make_source("gutenberg", formats=["epub", "txt"]),
                           make_config(tmp_path), FakeHttp())
    row = {"Text#": "1342", "Type": "Text", "Issued": "1998-06-01",
           "Title": "Pride and Prejudice", "Language": "en",
           "Authors": "Austen, Jane, 1775-1817",
           "Subjects": "Love stories; England -- Fiction",
           "LoCC": "PR", "Bookshelves": "Best Books Ever Listings"}
    r = c._parse(row, ["epub", "txt"])
    assert r.ext_id == "pg1342"
    assert r.categories == ["PR"]      # LoCC preferred over bookshelves/subjects
    assert r.download_url == "https://www.gutenberg.org/ebooks/1342.epub.images"
    assert r.file_ext == "epub"
    assert r.extra["alt_downloads"] == [("https://www.gutenberg.org/ebooks/1342.txt.utf-8", "txt")]


def test_internet_archive_parse_with_file_listing(tmp_path):
    search = {"response": {"numFound": 1, "docs": [{
        "identifier": "somebook", "title": "Some Book",
        "creator": "Anon", "subject": ["History", "War"],
        "year": "1901", "language": "eng",
        "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/",
    }]}}
    metadata = {"files": [
        {"name": "somebook.pdf", "format": "Text PDF"},
        {"name": "somebook_djvu.txt", "format": "DjVuTXT"},
    ]}
    http = FakeHttp(json_seq=[search, metadata])
    c = InternetArchiveConnector(make_source("internet_archive", formats=["Text PDF", "DjVuTXT"], max_records=1),
                                 make_config(tmp_path), http)
    r = list(c.iter_records())[0]
    assert r.ext_id == "somebook"
    assert r.categories == ["History"]
    assert r.download_url == "https://archive.org/download/somebook/somebook.pdf"
    assert r.file_ext == "pdf"
    assert r.extra["alt_downloads"] == [("https://archive.org/download/somebook/somebook_djvu.txt", "txt")]
