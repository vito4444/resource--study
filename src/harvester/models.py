"""Core data structures shared across connectors."""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Record:
    """A single harvestable resource (one paper or one ebook).

    ``ext_id`` is the source-native identifier (e.g. an arXiv id or a Project
    Gutenberg ebook number); the pair ``(source, ext_id)`` is globally unique
    and is what the state store keys on for resume/dedup.
    """

    source: str
    ext_id: str
    resource_type: str  # "paper" | "ebook"
    title: str = ""
    authors: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    language: str = ""
    published: str = ""
    license: str = ""
    landing_url: str = ""
    download_url: str = ""
    file_ext: str = ""
    description: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    # populated after a download attempt
    local_path: str = ""
    sha256: str = ""
    bytes: int = 0
    status: str = "pending"  # pending | metadata | downloaded | skipped | failed

    def category_segments(self) -> List[str]:
        """Return the category path segments used for the on-disk tree.

        Falls back to ``uncategorized`` so every record still lands somewhere.
        """
        segs = [c for c in self.categories if c and str(c).strip()]
        return segs if segs else ["uncategorized"]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Record":
        allowed = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})
