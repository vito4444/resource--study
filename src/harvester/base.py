"""Base class every source connector inherits from."""
from __future__ import annotations

from typing import Any, Iterator, List

from .config import Config, SourceConfig
from .http import HttpClient
from .models import Record


class BaseConnector:
    """A source of :class:`Record` objects.

    Subclasses set ``name`` and ``resource_type`` and implement
    :meth:`iter_records`, yielding metadata-complete records. Each record must
    carry a ``download_url`` and ``file_ext`` when the file is downloadable so
    the engine can fetch it; metadata-only sources leave those empty.
    """

    name: str = "base"
    resource_type: str = "paper"
    #: human-readable description shown by `harvester list-sources`
    description: str = ""

    def __init__(self, source_cfg: SourceConfig, config: Config, http: HttpClient) -> None:
        self.cfg = source_cfg
        self.config = config
        self.http = http

    @property
    def max_records(self) -> int:
        return self.cfg.max_records

    def opt(self, key: str, default: Any = None) -> Any:
        return self.cfg.get(key, default)

    def iter_records(self) -> Iterator[Record]:  # pragma: no cover - abstract
        raise NotImplementedError

    # small helpers shared by connectors
    @staticmethod
    def _as_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value if v is not None]
        return [str(value)]
