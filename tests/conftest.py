from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from harvester.config import Config, SourceConfig


class FakeHttp:
    """Stand-in for HttpClient that replays canned responses (no network)."""

    def __init__(self, json_seq: Optional[List[Any]] = None, text_seq: Optional[List[str]] = None):
        self.json_seq = list(json_seq or [])
        self.text_seq = list(text_seq or [])
        self.downloads: List[tuple] = []
        self.fail_urls: set = set()

    def get_json(self, url: str, params: Any = None, headers: Any = None) -> Any:
        return self.json_seq.pop(0) if self.json_seq else {}

    def get_text(self, url: str, params: Any = None, headers: Any = None) -> str:
        return self.text_seq.pop(0) if self.text_seq else ""

    def download(self, url: str, dest, overwrite: bool = False):
        if url in self.fail_urls:
            raise RuntimeError(f"simulated failure for {url}")
        self.downloads.append((url, str(dest)))
        p = Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"data")
        return 4, "0" * 64


def make_source(name: str, **options: Any) -> SourceConfig:
    reserved = {"enabled", "max_records", "download", "rate_limit_seconds"}
    return SourceConfig(
        name=name,
        enabled=options.pop("enabled", True),
        max_records=options.pop("max_records", 0),
        download=options.pop("download", True),
        rate_limit_seconds=options.pop("rate_limit_seconds", 0.0),
        options={k: v for k, v in options.items() if k not in reserved},
    )


def make_config(output_dir: Path, **kwargs: Any) -> Config:
    return Config(
        contact_email=kwargs.get("contact_email", "test@example.com"),
        output_dir=output_dir,
        download=kwargs.get("download", True),
        overwrite=kwargs.get("overwrite", False),
        global_max_records=kwargs.get("global_max_records", 0),
        default_per_source_max=kwargs.get("default_per_source_max", 200),
        request_timeout=kwargs.get("request_timeout", 60),
        retries=kwargs.get("retries", 4),
        sources=kwargs.get("sources", {}),
        raw={},
    )
