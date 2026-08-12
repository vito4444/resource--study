"""Harvest engine: drives connectors, enforces caps, downloads, records state."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from tqdm import tqdm

from . import connectors as _connectors  # noqa: F401  (registers built-in connectors)
from .config import Config, SourceConfig
from .http import HttpClient
from .models import Record
from .registry import get_connector
from .storage import Storage

log = logging.getLogger("harvester")

#: callback receiving structured progress events (dicts with a ``type`` key)
EventCallback = Optional[Callable[[dict], None]]
#: callback returning True when the caller wants the run to stop gracefully
StopCallback = Optional[Callable[[], bool]]


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
        on_event: EventCallback = None,
        should_stop: StopCallback = None,
    ) -> Dict[str, int]:
        """Harvest every enabled source.

        ``on_event`` (optional) is called with structured event dicts so a GUI
        can render live progress; ``should_stop`` (optional) is polled between
        records so a GUI can cancel gracefully. Neither affects CLI behaviour.
        """
        only_set = set(only) if only else None
        totals: Counter = Counter()
        global_cap = self.config.global_max_records
        harvested_global = 0
        stopped = False

        planned = [
            s for s in self.config.enabled_sources()
            if only_set is None or s.name in only_set
        ]
        _emit(on_event, type="run_start", sources=[s.name for s in planned], dry_run=dry_run)

        for src in planned:
            if _wants_stop(should_stop):
                stopped = True
                break
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
            _emit(on_event, type="source_start", source=src.name,
                  max_records=src.max_records)
            per_source = self._run_source(
                connector, src, http, dry_run, show_progress, global_cap,
                harvested_global, on_event, should_stop,
            )
            totals.update(per_source.counts)
            harvested_global += per_source.processed
            _emit(on_event, type="source_done", source=src.name,
                  counts=dict(per_source.counts))
            log.info(
                "%s: %s",
                src.name,
                ", ".join(f"{k}={v}" for k, v in sorted(per_source.counts.items())) or "nothing",
            )
            if per_source.stopped:
                stopped = True
                break
            if global_cap and harvested_global >= global_cap:
                break

        result = dict(totals)
        _emit(on_event, type="run_done", totals=result, stopped=stopped)
        return result

    def _run_source(
        self,
        connector,
        src: SourceConfig,
        http: HttpClient,
        dry_run: bool,
        show_progress: bool,
        global_cap: int,
        harvested_global: int,
        on_event: EventCallback = None,
        should_stop: StopCallback = None,
    ) -> "_SourceResult":
        counts: Counter = Counter()
        processed = 0
        stopped = False
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
                if _wants_stop(should_stop):
                    stopped = True
                    break
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
                    _emit_record(on_event, record, "skipped", processed)
                    continue

                if dry_run:
                    counts["preview"] += 1
                    processed += 1
                    bar.update(1)
                    tqdm.write(
                        f"[dry-run] {record.source} {record.ext_id} "
                        f"-> {'/'.join(record.category_segments())} | {record.title[:70]}"
                    )
                    _emit_record(on_event, record, "preview", processed)
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
                _emit_record(on_event, record, record.status, processed)
        except Exception as exc:  # keep partial progress on any source-level error
            log.error("%s failed mid-run: %s", src.name, exc)
            _emit(on_event, type="source_error", source=src.name, error=str(exc))
        finally:
            bar.close()

        return _SourceResult(counts=counts, processed=processed, stopped=stopped)

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
    __slots__ = ("counts", "processed", "stopped")

    def __init__(self, counts: Counter, processed: int, stopped: bool = False) -> None:
        self.counts = counts
        self.processed = processed
        self.stopped = stopped


def _emit(cb: EventCallback, **payload) -> None:
    if cb is None:
        return
    try:
        cb(payload)
    except Exception:  # a broken observer must never break the harvest
        log.debug("event callback raised", exc_info=True)


def _emit_record(cb: EventCallback, record: Record, status: str, processed: int) -> None:
    if cb is None:
        return
    _emit(
        cb,
        type="record",
        source=record.source,
        resource_type=record.resource_type,
        ext_id=record.ext_id,
        title=record.title,
        category="/".join(record.category_segments()),
        status=status,
        bytes=record.bytes,
        local_path=record.local_path,
        processed=processed,
    )


def _wants_stop(cb: StopCallback) -> bool:
    if cb is None:
        return False
    try:
        return bool(cb())
    except Exception:
        return False
