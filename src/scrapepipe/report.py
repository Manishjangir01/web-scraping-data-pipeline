"""Run the queries in sql/analytics.sql and print them as tables."""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQL = ROOT / "sql" / "analytics.sql"
_NAME = re.compile(r"--\s*name:\s*(\w+)")


def load_queries(path: str | Path) -> list[tuple[str, str]]:
    """Return ``[(name, sql), ...]``. Each query needs a ``-- name: x`` comment."""
    queries = []
    for block in Path(path).read_text().split(";"):
        match = _NAME.search(block)
        sql = "\n".join(
            line for line in block.splitlines() if not line.strip().startswith("--")
        ).strip()
        if match and sql:
            queries.append((match.group(1), sql))
    return queries


def format_table(columns: list[str], rows: list[tuple]) -> str:
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max([len(c)] + [len(r[i]) for r in cells]) for i, c in enumerate(columns)]
    line = "  ".join(c.ljust(w) for c, w in zip(columns, widths))
    rule = "  ".join("-" * w for w in widths)
    body = ["  ".join(v.ljust(w) for v, w in zip(r, widths)) for r in cells]
    return "\n".join([line, rule, *body]) if body else "\n".join([line, rule, "(no rows)"])


def report(db_path: str | Path, sql_path: str | Path = DEFAULT_SQL, out=None) -> int:
    """Print every query in the SQL file. Returns the number of queries run."""
    out = out or sys.stdout
    conn = sqlite3.connect(db_path)
    try:
        queries = load_queries(sql_path)
        for name, sql in queries:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description]
            print(f"\n== {name} ==", file=out)
            print(format_table(columns, cur.fetchall()), file=out)
    finally:
        conn.close()
    return len(queries)
