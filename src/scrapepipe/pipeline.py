"""The whole pipeline: scrape -> raw file -> clean and validate -> SQLite."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from scrapepipe import config, store
from scrapepipe.clean import clean_records
from scrapepipe.fetcher import Fetcher, FetchError
from scrapepipe.parser import parse_listing

log = logging.getLogger("scrapepipe")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _write_raw(raw_dir: str | Path, run_id: int, records: list[dict]) -> str:
    """Keep exactly what was scraped, one JSON object per line (the "bronze" layer)."""
    path = Path(raw_dir)
    path.mkdir(parents=True, exist_ok=True)
    file = path / f"books_run{run_id:04d}.jsonl"
    with open(file, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return str(file)


def run(
    start_url: str = config.BASE_URL,
    db_path: str | Path = "data/books.db",
    raw_dir: str | Path = "data/raw",
    max_pages: int = 3,
    fetcher: Fetcher | None = None,
) -> dict:
    """Scrape up to ``max_pages`` listing pages and store the result.

    ``status`` in the returned summary is one of:
    ``ok``, ``partial`` (a later page failed, earlier pages were still saved),
    ``failed`` (the first page failed) or ``empty`` (pages loaded but held no books,
    which usually means the site's markup changed).
    """
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    fetcher = fetcher or Fetcher()
    started = _now()
    conn = store.connect(db_path)
    run_id = store.start_run(conn, started)

    raw_records: list[dict] = []
    pages = 0
    status = "ok"
    error = None
    url: str | None = start_url
    visited: set[str] = set()

    while url and pages < max_pages and url not in visited:
        visited.add(url)
        try:
            html = fetcher.get(url)
        except FetchError as exc:
            status = "partial" if pages else "failed"
            error = str(exc)
            log.error("%s", exc)
            break
        records, next_url = parse_listing(html, url)
        for rec in records:
            rec["scraped_at"] = started
        raw_records.extend(records)
        pages += 1
        log.info("page %s: %s books", pages, len(records))
        url = next_url

    if status == "ok" and not raw_records:
        status = "empty"
        error = "pages loaded but no books were found"
        log.warning(error)

    raw_file = _write_raw(raw_dir, run_id, raw_records) if raw_records else None
    clean, rejected = clean_records(raw_records, scraped_at=started)
    new_books, price_changes = store.upsert_books(conn, clean, started)
    store.save_rejected(conn, run_id, rejected)
    store.finish_run(
        conn,
        run_id,
        _now(),
        status,
        pages_fetched=pages,
        raw_records=len(raw_records),
        clean_records=len(clean),
        rejected_records=len(rejected),
        new_books=new_books,
        price_changes=price_changes,
    )
    conn.close()

    summary = {
        "run_id": run_id,
        "status": status,
        "pages_fetched": pages,
        "raw_records": len(raw_records),
        "clean_records": len(clean),
        "rejected_records": len(rejected),
        "new_books": new_books,
        "price_changes": price_changes,
        "raw_file": raw_file,
    }
    if error:
        summary["error"] = error
    log.info("run %s finished: %s", run_id, status)
    return summary
