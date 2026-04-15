from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from personal_digest.bootstrap import create_application
from personal_digest.logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal Digest Agent CLI")
    parser.add_argument("--config-dir", default="config", help="Directory containing settings.yaml and sources.yaml")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Initialize the SQLite database schema")
    subparsers.add_parser("sync-sources", help="Sync YAML sources into SQLite")
    subparsers.add_parser("poll", help="Run feed polling, extraction, and analysis pipeline")

    digest_parser = subparsers.add_parser("digest", help="Build digest and optionally send email")
    digest_parser.add_argument("--date", dest="digest_date", help="Digest date in YYYY-MM-DD")
    digest_parser.add_argument("--send", action="store_true", help="Send the digest email after building")

    run_once_parser = subparsers.add_parser("run-once", help="Run the entire pipeline once and send digest")
    run_once_parser.add_argument("--date", dest="digest_date", help="Digest date in YYYY-MM-DD")

    subparsers.add_parser("serve", help="Start the blocking APScheduler service")
    return parser


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    config_dir = Path(args.config_dir).resolve()
    app = create_application(config_dir)

    if args.command == "init-db":
        app.database.initialize()
        print(json.dumps({"database": str(app.database.path), "status": "initialized"}, ensure_ascii=False))
        return

    if args.command == "sync-sources":
        count = app.pipeline.sync_sources()
        print(json.dumps({"synced_sources": count}, ensure_ascii=False))
        return

    if args.command == "poll":
        print(json.dumps(app.pipeline.run_poll_cycle(), ensure_ascii=False))
        return

    if args.command == "digest":
        digest_date = _parse_digest_date(args.digest_date)
        print(json.dumps(app.pipeline.run_digest_cycle(digest_date, send=args.send), ensure_ascii=False))
        return

    if args.command == "run-once":
        digest_date = _parse_digest_date(args.digest_date)
        print(json.dumps(app.pipeline.run_once(digest_date), ensure_ascii=False))
        return

    if args.command == "serve":
        app.scheduler.run()
        return

    parser.error(f"Unknown command: {args.command}")


def _parse_digest_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None

