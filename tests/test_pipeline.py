import json
import sqlite3
from collections import Counter

from helpers import PAGE_1, build_page

from scrapepipe import pipeline
from scrapepipe.fetcher import Fetcher, build_session


def make_fetcher(**kwargs):
    kwargs.setdefault("delay", 0)
    return Fetcher(session=build_session(retries=2, backoff=0), **kwargs)


def run(site, tmp_path, **kwargs):
    kwargs.setdefault("max_pages", 3)
    return pipeline.run(
        start_url=site.base_url,
        db_path=tmp_path / "books.db",
        raw_dir=tmp_path / "raw",
        fetcher=kwargs.pop("fetcher", None) or make_fetcher(),
        **kwargs,
    )


def query(tmp_path, sql):
    conn = sqlite3.connect(tmp_path / "books.db")
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_full_run_over_three_pages(site, tmp_path):
    summary = run(site, tmp_path)

    assert summary["status"] == "ok"
    assert summary["pages_fetched"] == 3
    assert summary["raw_records"] == 14
    assert summary["clean_records"] == 11
    assert summary["rejected_records"] == 3
    assert summary["new_books"] == 11

    assert query(tmp_path, "SELECT COUNT(*) FROM books") == [(11,)]
    reasons = Counter(r[0] for r in query(tmp_path, "SELECT reject_reason FROM rejected_records"))
    assert reasons == {"duplicate_url": 1, "invalid_price": 1, "invalid_rating": 1}

    # The "£" that came through as "Â£" was still parsed.
    assert query(tmp_path, "SELECT price FROM books WHERE title LIKE 'Scott Pilgrim%'") == [(52.29,)]
    # Only the one "Out of stock" book is marked as not in stock.
    assert query(tmp_path, "SELECT COUNT(*) FROM books WHERE in_stock = 0") == [(1,)]

    run_row = query(tmp_path, "SELECT status, pages_fetched, clean_records FROM scrape_runs")
    assert run_row == [("ok", 3, 11)]


def test_raw_records_are_saved_untouched(site, tmp_path):
    summary = run(site, tmp_path)
    lines = open(summary["raw_file"], encoding="utf-8").read().splitlines()
    assert len(lines) == 14
    records = [json.loads(line) for line in lines]
    assert any(r["price_text"] == "Â£52.29" for r in records)  # kept as scraped
    assert any(r["price_text"] is None for r in records)


def test_second_run_creates_no_duplicates(site, tmp_path):
    run(site, tmp_path)
    second = run(site, tmp_path)

    assert second["new_books"] == 0
    assert second["price_changes"] == 0
    assert query(tmp_path, "SELECT COUNT(*) FROM books") == [(11,)]
    assert query(tmp_path, "SELECT COUNT(*) FROM price_history") == [(11,)]
    assert query(tmp_path, "SELECT COUNT(*) FROM scrape_runs") == [(2,)]


def test_price_change_between_runs_is_tracked(site, tmp_path):
    run(site, tmp_path)
    changed = [(t, "£99.99" if t == "Soumission" else p, r, a) for t, p, r, a in PAGE_1]
    site.pages["/"] = build_page_with_same_urls(changed)

    second = run(site, tmp_path)

    assert second["price_changes"] == 1
    assert query(tmp_path, "SELECT price FROM books WHERE title = 'Soumission'") == [(99.99,)]
    history = query(
        tmp_path,
        "SELECT h.price FROM price_history h JOIN books b ON b.url = h.url "
        "WHERE b.title = 'Soumission' ORDER BY h.observed_at",
    )
    assert history == [(50.10,), (99.99,)]


def build_page_with_same_urls(books):
    return build_page(books, "catalogue/", "catalogue/page-2.html")


def test_max_pages_is_respected(site, tmp_path):
    summary = run(site, tmp_path, max_pages=2)
    assert summary["pages_fetched"] == 2
    assert summary["raw_records"] == 10
    assert site.hits["/catalogue/page-3.html"] == 0


def test_failure_on_a_later_page_keeps_the_earlier_pages(site, tmp_path):
    site.fail_next["/catalogue/page-3.html"] = 99
    summary = run(site, tmp_path)

    assert summary["status"] == "partial"
    assert summary["pages_fetched"] == 2
    assert "page-3" in summary["error"]
    assert summary["clean_records"] == 9  # 10 raw rows, one is a duplicate
    assert query(tmp_path, "SELECT COUNT(*) FROM books") == [(9,)]
    assert query(tmp_path, "SELECT status FROM scrape_runs") == [("partial",)]


def test_failure_on_the_first_page_is_reported(site, tmp_path):
    site.fail_next["/"] = 99
    summary = run(site, tmp_path)
    assert summary["status"] == "failed"
    assert summary["pages_fetched"] == 0
    assert summary["raw_file"] is None
    assert query(tmp_path, "SELECT COUNT(*) FROM books") == [(0,)]


def test_robots_txt_blocking_everything_gives_a_failed_run(site, tmp_path):
    site.robots = "User-agent: *\nDisallow: /\n"
    summary = run(site, tmp_path)
    assert summary["status"] == "failed"
    assert "robots.txt" in summary["error"]
    assert site.hits["/"] == 0


def test_page_without_books_is_flagged_as_empty(site, tmp_path):
    site.pages["/"] = "<html><body><p>The layout changed</p></body></html>"
    summary = run(site, tmp_path)
    assert summary["status"] == "empty"
    assert query(tmp_path, "SELECT status FROM scrape_runs") == [("empty",)]


def test_max_pages_must_be_positive(site, tmp_path):
    import pytest

    with pytest.raises(ValueError):
        run(site, tmp_path, max_pages=0)
