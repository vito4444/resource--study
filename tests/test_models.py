from __future__ import annotations

import json

from harvester.models import Record


def test_category_segments_fallback():
    assert Record(source="s", ext_id="1", resource_type="paper").category_segments() == ["uncategorized"]
    assert Record(source="s", ext_id="1", resource_type="paper",
                  categories=["a", "", "b"]).category_segments() == ["a", "b"]


def test_roundtrip_json():
    rec = Record(source="arxiv", ext_id="2401.1", resource_type="paper",
                 title="Hello", authors=["A", "B"], categories=["cs", "AI"],
                 extra={"k": "v"})
    data = json.loads(rec.to_json())
    again = Record.from_dict(data)
    assert again == rec


def test_from_dict_ignores_unknown_keys():
    rec = Record.from_dict({"source": "s", "ext_id": "1", "resource_type": "paper",
                            "unexpected": 123})
    assert rec.source == "s" and rec.ext_id == "1"
