"""Command line: ``python -m scrapepipe run`` and ``python -m scrapepipe report``."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from scrapepipe import config, pipeline, report
from scrapepipe.fetcher import Fetcher, build_session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scrapepipe", description="Scrape, clean and store book data.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="scrape listing pages and store the books")
    run.add_argument("--start-url", default=config.BASE_URL)
    run.add_argument("--db", default="data/books.db", help="SQLite file")
    run.add_argument("--raw-dir", default="data/raw", help="folder for the raw JSON lines files")
    run.add_argument("--max-pages", type=int, default=3)
    run.add_argument("--delay", type=float, default=config.DEFAULT_DELAY, help="seconds between requests")
    run.add_argument("--retries", type=int, default=config.MAX_RETRIES)
    run.add_argument("--backoff", type=float, default=config.BACKOFF_FACTOR)

    rep = sub.add_parser("report", help="print the SQL analytics")
    rep.add_argument("--db", default="data/books.db")
    rep.add_argument("--sql", default=str(report.DEFAULT_SQL))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "run":
        session = build_session(retries=args.retries, backoff=args.backoff)
        fetcher = Fetcher(session=session, delay=args.delay)
        summary = pipeline.run(
            start_url=args.start_url,
            db_path=args.db,
            raw_dir=args.raw_dir,
            max_pages=args.max_pages,
            fetcher=fetcher,
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary["status"] == "ok" else 1

    report.report(args.db, args.sql)
    return 0


if __name__ == "__main__":
    sys.exit(main())
