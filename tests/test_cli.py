import contextlib
import io
import json

from scrapepipe import report
from scrapepipe.cli import main


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


def scrape(site, tmp_path, *extra):
    return run_cli(
        "run",
        "--start-url", site.base_url,
        "--db", str(tmp_path / "books.db"),
        "--raw-dir", str(tmp_path / "raw"),
        "--delay", "0",
        "--backoff", "0",
        *extra,
    )


def test_run_command_prints_a_summary_and_exits_zero(site, tmp_path):
    code, output = scrape(site, tmp_path)
    summary = json.loads(output)
    assert code == 0
    assert summary["status"] == "ok"
    assert summary["clean_records"] == 11


def test_run_command_exits_non_zero_when_a_page_fails(site, tmp_path):
    site.fail_next["/catalogue/page-2.html"] = 99
    code, output = scrape(site, tmp_path, "--retries", "1")
    assert code == 1
    assert json.loads(output)["status"] == "partial"


def test_report_command_prints_every_query(site, tmp_path):
    scrape(site, tmp_path)
    code, output = run_cli("report", "--db", str(tmp_path / "books.db"))
    assert code == 0
    for name in (
        "price_by_rating",
        "stock_summary",
        "price_bands",
        "cheapest_five_star_in_stock",
        "price_changes",
        "latest_runs",
    ):
        assert f"== {name} ==" in output
    assert "Sapiens: A Brief History of Humankind" in output


def test_analytics_numbers_are_right(site, tmp_path):
    scrape(site, tmp_path)
    import sqlite3

    conn = sqlite3.connect(tmp_path / "books.db")
    queries = dict(report.load_queries(report.DEFAULT_SQL))

    by_rating = {r[0]: (r[1], r[2]) for r in conn.execute(queries["price_by_rating"])}
    assert by_rating[5] == (2, 53.26)  # Sapiens 54.23 and Scott Pilgrim 52.29
    # Tipping 53.74, Soumission 50.10, Requiem Red 22.65 and Olio 23.88: 150.37 / 4 = 37.59
    assert by_rating[1] == (4, 37.59)

    stock = {r[0]: r[1] for r in conn.execute(queries["stock_summary"])}
    assert stock == {"in stock": 10, "out of stock": 1}

    bands = dict(conn.execute(queries["price_bands"]).fetchall())
    assert sum(bands.values()) == 11
    conn.close()


def test_format_table_aligns_columns_and_handles_no_rows():
    text = report.format_table(["name", "n"], [("a", 1), ("longer", None)])
    assert text.splitlines()[0].split() == ["name", "n"]
    assert "longer" in text
    assert report.format_table(["x"], []).endswith("(no rows)")
