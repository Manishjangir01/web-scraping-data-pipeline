"""SQLite storage: current books, price history, rejected rows and run log."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    url        TEXT PRIMARY KEY,
    title      TEXT    NOT NULL,
    price      REAL    NOT NULL CHECK (price > 0),
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    in_stock   INTEGER NOT NULL CHECK (in_stock IN (0, 1)),
    first_seen TEXT    NOT NULL,
    last_seen  TEXT    NOT NULL
);

-- One row when a book is first seen and one more each time its price changes.
CREATE TABLE IF NOT EXISTS price_history (
    url         TEXT NOT NULL REFERENCES books(url),
    price       REAL NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (url, observed_at)
);

CREATE TABLE IF NOT EXISTS rejected_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            INTEGER NOT NULL,
    reject_reason     TEXT    NOT NULL,
    title             TEXT,
    url               TEXT,
    price_text        TEXT,
    rating_text       TEXT,
    availability_text TEXT,
    page_url          TEXT,
    scraped_at        TEXT
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT,
    pages_fetched    INTEGER,
    raw_records      INTEGER,
    clean_records    INTEGER,
    rejected_records INTEGER,
    new_books        INTEGER,
    price_changes    INTEGER
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (and create if needed) the database."""
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def start_run(conn: sqlite3.Connection, started_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO scrape_runs (started_at, status) VALUES (?, 'running')", (started_at,)
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, finished_at: str, status: str, **counts) -> None:
    conn.execute(
        """UPDATE scrape_runs
           SET finished_at = ?, status = ?, pages_fetched = ?, raw_records = ?,
               clean_records = ?, rejected_records = ?, new_books = ?, price_changes = ?
           WHERE run_id = ?""",
        (
            finished_at,
            status,
            counts["pages_fetched"],
            counts["raw_records"],
            counts["clean_records"],
            counts["rejected_records"],
            counts["new_books"],
            counts["price_changes"],
            run_id,
        ),
    )
    conn.commit()


def upsert_books(conn: sqlite3.Connection, rows: list[dict], observed_at: str) -> tuple[int, int]:
    """Insert new books and update known ones. Returns ``(new_books, price_changes)``.

    Running it twice with the same rows changes nothing except ``last_seen``, so a
    repeated run never creates duplicates. A price_history row is only added when
    the price is different from the last one we saw.
    """
    new_books = 0
    price_changes = 0
    for row in rows:
        existing = conn.execute("SELECT price FROM books WHERE url = ?", (row["url"],)).fetchone()
        if existing is None:
            conn.execute(
                """INSERT INTO books (url, title, price, rating, in_stock, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (row["url"], row["title"], row["price"], row["rating"], int(row["in_stock"]),
                 observed_at, observed_at),
            )
            conn.execute(
                "INSERT INTO price_history (url, price, observed_at) VALUES (?, ?, ?)",
                (row["url"], row["price"], observed_at),
            )
            new_books += 1
            continue

        conn.execute(
            """UPDATE books SET title = ?, price = ?, rating = ?, in_stock = ?, last_seen = ?
               WHERE url = ?""",
            (row["title"], row["price"], row["rating"], int(row["in_stock"]), observed_at, row["url"]),
        )
        if abs(existing["price"] - row["price"]) > 1e-9:
            conn.execute(
                "INSERT INTO price_history (url, price, observed_at) VALUES (?, ?, ?)",
                (row["url"], row["price"], observed_at),
            )
            price_changes += 1
    conn.commit()
    return new_books, price_changes


def save_rejected(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO rejected_records
           (run_id, reject_reason, title, url, price_text, rating_text, availability_text,
            page_url, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                run_id,
                r["reject_reason"],
                r.get("title"),
                r.get("url"),
                r.get("price_text"),
                r.get("rating_text"),
                r.get("availability_text"),
                r.get("page_url"),
                r.get("scraped_at"),
            )
            for r in rows
        ],
    )
    conn.commit()
