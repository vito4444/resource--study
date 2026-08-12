"""Command-line interface for the resource-study-harvester."""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, connectors as _connectors  # noqa: F401  (registers connectors)
from .config import load_config
from .harvest import Harvester
from .registry import available
from .storage import Storage

_EXAMPLE_CONFIG = Path(__file__).resolve().parents[2] / "config.example.yaml"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_list_sources(args: argparse.Namespace) -> int:
    reg = available()
    print(f"{len(reg)} built-in sources:\n")
    for name in sorted(reg):
        cls = reg[name]
        print(f"  {name:<18} [{cls.resource_type}]  {cls.description}")
    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
    dest = Path(args.output)
    if dest.exists() and not args.force:
        print(f"refusing to overwrite existing {dest} (use --force)", file=sys.stderr)
        return 1
    shutil.copyfile(_EXAMPLE_CONFIG, dest)
    print(f"wrote {dest} — edit it, then run: harvester harvest --config {dest}")
    return 0


def _overrides_from_args(args: argparse.Namespace) -> dict:
    overrides: dict = {}
    if getattr(args, "output", None):
        overrides["output_dir"] = args.output
    if getattr(args, "contact", None):
        overrides["contact_email"] = args.contact
    if getattr(args, "no_download", False):
        overrides["download"] = False
    return overrides


def cmd_harvest(args: argparse.Namespace) -> int:
    config = load_config(args.config, overrides=_overrides_from_args(args))
    if args.max is not None:
        for src in config.sources.values():
            src.max_records = args.max
    if not config.sources:
        print(
            "no sources configured. Run `harvester init-config` and edit config.yaml, "
            "or pass --config.",
            file=sys.stderr,
        )
        return 1

    only = _split_csv(args.only)
    harvester = Harvester(config)
    try:
        totals = harvester.run(only=only, dry_run=args.dry_run, show_progress=not args.quiet)
    finally:
        harvester.close()

    print("\n=== harvest summary ===")
    if not totals:
        print("(nothing processed)")
    for status in sorted(totals):
        print(f"  {status:<12} {totals[status]}")
    print(f"output dir: {config.output_dir.resolve()}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    storage = Storage(Path(args.output))
    try:
        counts = storage.counts_by_status()
        total = storage.total()
    finally:
        storage.close()
    print(f"records tracked: {total}")
    for status in sorted(counts):
        print(f"  {status:<12} {counts[status]}")
    catalog_dir = Path(args.output) / "catalog"
    if catalog_dir.exists():
        print("\ncatalog files:")
        for f in sorted(catalog_dir.glob("*.jsonl")):
            lines = sum(1 for _ in f.open("r", encoding="utf-8"))
            print(f"  {f.name:<24} {lines} records")
    return 0


def _split_csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harvester",
        description="Categorized bulk downloader for open-access papers and "
        "public-domain / free ebooks.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-sources", help="list available source connectors")
    p_list.set_defaults(func=cmd_list_sources)

    p_init = sub.add_parser("init-config", help="write a starter config.yaml")
    p_init.add_argument("-o", "--output", default="config.yaml", help="destination path")
    p_init.add_argument("--force", action="store_true", help="overwrite if it exists")
    p_init.set_defaults(func=cmd_init_config)

    p_harvest = sub.add_parser("harvest", help="run a harvest")
    p_harvest.add_argument("-c", "--config", default=None, help="path to config.yaml")
    p_harvest.add_argument("--only", default=None, help="comma-separated subset of sources")
    p_harvest.add_argument("--max", type=int, default=None, help="override per-source cap (0 = unlimited)")
    p_harvest.add_argument("--output", default=None, help="override output dir")
    p_harvest.add_argument("--contact", default=None, help="override contact email")
    p_harvest.add_argument("--no-download", action="store_true", help="metadata only")
    p_harvest.add_argument("--dry-run", action="store_true", help="preview without downloading")
    p_harvest.add_argument("--quiet", action="store_true", help="no progress bars")
    p_harvest.set_defaults(func=cmd_harvest)

    p_stats = sub.add_parser("stats", help="show harvested totals from the state db")
    p_stats.add_argument("-o", "--output", default="data", help="output dir to inspect")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
