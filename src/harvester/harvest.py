"""Harvest engine: drives connectors, enforces caps, downloads, records state."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

from tqdm import tqdm

from . import connectors as _connectors  # noqa: F401  (registers built-in connectors)
from .config import Config, SourceConfig
from .http import HttpClient
from .models import Record
from .registry import get_connector
from .storage import Storage

log = logging.getLogger("harvester")


class Harvester:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.storage = Storage(config.output_dir)

    def close(self) -> None:
        self.storage.close()

    def run(
        self,
        only: Optional[Iterable[str]] = None,
        dry_run: bool = False,
        show_progress: bool = True,
    ) -> Dict[str, int]:
        only_set = set(only) if only else None
        totals: Counter = Counter()
        global_cap = self.config.global_max_records
        harvested_global = 0

        for src in self.config.enabled_sources():
            if only_set is not None and src.name not in only_set:
                continue
            try:
                connector_cls = get_connector(src.name)
            except KeyError:
                log.warning("unknown connector '%s' (skipped)", src.name)
                continue

            http = HttpClient(
                contact_email=self.config.contact_email,
                timeout=self.config.request_timeout,
                retries=self.config.retries,
                rate_limit_seconds=src.rate_limit_seconds,
            )
            connector = connector_cls(src, self.config, http)
            per_source = self._run_source(
                connector, src, http, dry_run, show_progress, global_cap, harvested_global
            )
            totals.update(per_source.counts)
            harvested_global += per_source.processed
            log.info(
                "%s: %s",
                src.name,
                ", ".join(f"{k}={v}" for k, v in sorted(per_source.counts.items())) or "nothing",
            )
            if global_cap and harvested_global >= global_cap:
                break

        return dict(totals)

    def _run_source(
        self,
        connector,
        src: SourceConfig,
        http: HttpClient,
        dry_run: bool,
        show_progress: bool,
        global_cap: int,
        harvested_global: int,
    ) -> "_SourceResult":
        counts: Counter = Counter()
        processed = 0
        per_cap = src.max_records
        want_download = self.config.download and src.download

        bar = tqdm(
            desc=src.name,
            unit="rec",
            total=per_cap if per_cap else None,
            disable=not show_progress,
        )
        try:
            for record in connector.iter_records():
                if per_cap and processed >= per_cap:
                    break
                if global_cap and (harvested_global + processed) >= global_cap:
                    break

                has_file = bool(record.download_url or record.extra.get("alt_downloads"))
                need_dl = want_download and has_file

                if self.storage.is_done(record.source, record.ext_id, need_dl):
                    counts["skipped"] += 1
                    processed += 1
                    bar.update(1)
                    continue

                if dry_run:
                    counts["preview"] += 1
                    processed += 1
                    bar.update(1)
                    tqdm.write(
                        f"[dry-run] {record.source} {record.ext_id} "
                        f"-> {'/'.join(record.category_segments())} | {record.title[:70]}"
                    )
                    continue

                record.status = "metadata"
                if need_dl:
                    ok = self._download(record, http)
                    record.status = "downloaded" if ok else "failed"

                self.storage.append_catalog(record)
                self.storage.mark(record)
                counts[record.status] += 1
                processed += 1
                bar.update(1)
        except Exception as exc:  # keep partial progress on any source-level error
            log.error("%s failed mid-run: %s", src.name, exc)
        finally:
            bar.close()

        return _SourceResult(counts=counts, processed=processed)

    def _download(self, record: Record, http: HttpClient) -> bool:
        candidates: List[Tuple[str, str]] = []
        if record.download_url:
            candidates.append((record.download_url, record.file_ext))
        candidates.extend(record.extra.get("alt_downloads", []) or [])

        for url, ext in candidates:
            if not url:
                continue
            record.file_ext = ext or record.file_ext or "bin"
            dest = self.storage.path_for(record)
            try:
                size, sha = http.download(url, dest, overwrite=self.config.overwrite)
            except Exception as exc:
                log.debug("download failed %s (%s): %s", record.ext_id, url, exc)
                continue
            if size > 0:
                record.local_path = str(dest)
                record.bytes = size
                record.sha256 = sha
                record.download_url = url
                return True
        return False


class _SourceResult:
    __slots__ = ("counts", "processed")

    def __init__(self, counts: Counter, processed: int) -> None:
        self.counts = counts
        self.processed = processed
