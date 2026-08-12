from __future__ import annotations

import textwrap

from harvester.config import load_config


def test_defaults_when_no_file():
    cfg = load_config(None)
    assert cfg.contact_email == "anonymous@example.com"
    assert cfg.download is True
    assert cfg.sources == {}


def test_load_file_and_source_option_split(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(textwrap.dedent(
        """
        contact_email: me@example.com
        output_dir: out
        sources:
          arxiv:
            enabled: true
            max_records: 5
            rate_limit_seconds: 3.0
            categories: [cs.AI, math.AG]
          crossref:
            enabled: false
        """
    ), encoding="utf-8")
    cfg = load_config(p)
    assert cfg.contact_email == "me@example.com"
    assert str(cfg.output_dir) == "out"
    arxiv = cfg.sources["arxiv"]
    assert arxiv.max_records == 5
    assert arxiv.rate_limit_seconds == 3.0
    # non-reserved keys land in options, reserved keys do not
    assert arxiv.get("categories") == ["cs.AI", "math.AG"]
    assert "max_records" not in arxiv.options
    assert [s.name for s in cfg.enabled_sources()] == ["arxiv"]


def test_overrides_win_over_file(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("download: true\ncontact_email: file@x.com\n", encoding="utf-8")
    cfg = load_config(p, overrides={"download": False, "contact_email": "cli@x.com"})
    assert cfg.download is False
    assert cfg.contact_email == "cli@x.com"
