"""Configuration loading and normalization."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFAULTS: Dict[str, Any] = {
    "contact_email": "anonymous@example.com",
    "output_dir": "data",
    "download": True,
    "overwrite": False,
    "global_max_records": 0,
    "default_per_source_max": 200,
    "request_timeout": 60,
    "retries": 4,
    "sources": {},
}


@dataclass
class SourceConfig:
    name: str
    enabled: bool = True
    max_records: int = 200
    download: bool = True
    rate_limit_seconds: float = 1.0
    options: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)


@dataclass
class Config:
    contact_email: str
    output_dir: Path
    download: bool
    overwrite: bool
    global_max_records: int
    default_per_source_max: int
    request_timeout: int
    retries: int
    sources: Dict[str, SourceConfig]
    raw: Dict[str, Any] = field(default_factory=dict)

    def enabled_sources(self) -> List[SourceConfig]:
        return [s for s in self.sources.values() if s.enabled]


# keys that live directly on SourceConfig; everything else is a connector option
_SOURCE_RESERVED = {"enabled", "max_records", "download", "rate_limit_seconds"}


def _build_source(name: str, data: Dict[str, Any], defaults: Dict[str, Any]) -> SourceConfig:
    data = data or {}
    options = {k: v for k, v in data.items() if k not in _SOURCE_RESERVED}
    return SourceConfig(
        name=name,
        enabled=bool(data.get("enabled", True)),
        max_records=int(data.get("max_records", defaults["default_per_source_max"])),
        download=bool(data.get("download", defaults["download"])),
        rate_limit_seconds=float(data.get("rate_limit_seconds", 1.0)),
        options=options,
    )


def load_config_from_mapping(
    loaded: Optional[Dict[str, Any]] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Config:
    """Build a :class:`Config` from a parsed mapping merged over defaults.

    ``overrides`` win over ``loaded``, which wins over the built-in defaults.
    """
    merged: Dict[str, Any] = copy.deepcopy(DEFAULTS)
    if loaded:
        if not isinstance(loaded, dict):
            raise ValueError("config root must be a mapping")
        for key, value in loaded.items():
            if key == "sources" and isinstance(value, dict):
                merged["sources"] = value
            else:
                merged[key] = value

    if overrides:
        for key, value in overrides.items():
            if value is not None:
                merged[key] = value

    sources: Dict[str, SourceConfig] = {}
    for name, data in (merged.get("sources") or {}).items():
        sources[name] = _build_source(name, data, merged)

    return Config(
        contact_email=str(merged["contact_email"]),
        output_dir=Path(merged["output_dir"]),
        download=bool(merged["download"]),
        overwrite=bool(merged["overwrite"]),
        global_max_records=int(merged["global_max_records"]),
        default_per_source_max=int(merged["default_per_source_max"]),
        request_timeout=int(merged["request_timeout"]),
        retries=int(merged["retries"]),
        sources=sources,
        raw=merged,
    )


def _mapping_from_text(text: str) -> Dict[str, Any]:
    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ValueError("config root must be a mapping")
    return loaded


def load_config(path: Optional[str | Path] = None, overrides: Optional[Dict[str, Any]] = None) -> Config:
    """Load a YAML config file merged over defaults, then apply overrides."""
    loaded: Dict[str, Any] = {}
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"config file not found: {p}")
        loaded = _mapping_from_text(p.read_text(encoding="utf-8"))
    return load_config_from_mapping(loaded, overrides)


def default_config_text() -> str:
    """Return the packaged starter config as text (works when frozen too)."""
    return resources.files("harvester.resources").joinpath("default_config.yaml").read_text(
        encoding="utf-8"
    )


def load_default_config(overrides: Optional[Dict[str, Any]] = None) -> Config:
    """Load the packaged default config (used by the GUI and `init-config`)."""
    return load_config_from_mapping(_mapping_from_text(default_config_text()), overrides)
