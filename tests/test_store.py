import sqlite3

import pytest

from scrapepipe import store


def row(url="http://shop.test/1", price=10.0, **kw):
    base = {"title": "A Book", "url": url, "price": price, "rating": 3, "in_stock": True}
    base.update(kw)
    return base


@pytest.fixture
def conn(tmp_path):
    c = store.connect(tmp_path / "books.db")
    yield c
    c.close()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_new_book_is_inserted_with_a_first_price(conn):
    assert store.upsert_books(conn, [row()], "t1") == (1, 0)
    assert count(conn, "books") == 1
    assert count(conn, "price_history") == 1


def test_same_data_twice_creates_no_duplicates(conn):
    store.upsert_books(conn, [row(), row(url="http://shop.test/2")], "t1")
    assert store.upsert_books(conn, [row(), row(url="http://shop.test/2")], "t2") == (0, 0)
    assert count(conn, "books") == 2
    assert count(conn, "price_history") == 2
    assert conn.execute("SELECT first_seen, last_seen FROM books WHERE url = 'http://shop.test/1'").fetchone()[:] == ("t1", "t2")


def test_price_change_is_recorded_in_the_history(conn):
    store.upsert_books(conn, [row(price=10.0)], "t1")
    assert store.upsert_books(conn, [row(price=12.5)], "t2") == (0, 1)
    assert conn.execute("SELECT price FROM books").fetchone()[0] == 12.5
    prices = [r[0] for r in conn.execute("SELECT price FROM price_history ORDER BY observed_at")]
    assert prices == [10.0, 12.5]


def test_other_fields_are_updated_without_a_price_change(conn):
    store.upsert_books(conn, [row(in_stock=True, rating=3)], "t1")
    assert store.upsert_books(conn, [row(in_stock=False, rating=4)], "t2") == (0, 0)
    assert tuple(conn.execute("SELECT in_stock, rating FROM books").fetchone()) == (0, 4)
    assert count(conn, "price_history") == 1


def test_database_constraints_reject_bad_rows(conn):
    with pytest.raises(sqlite3.IntegrityError):
        store.upsert_books(conn, [row(price=-1.0)], "t1")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        store.upsert_books(conn, [row(rating=9)], "t1")


def test_rejected_rows_are_saved_with_the_run_id(conn):
    run_id = store.start_run(conn, "t1")
    store.save_rejected(
        conn,
        run_id,
        [{"reject_reason": "invalid_price", "title": "X", "price_text": "n/a", "scraped_at": "t1"}],
    )
    saved = conn.execute("SELECT run_id, reject_reason, price_text FROM rejected_records").fetchone()
    assert tuple(saved) == (run_id, "invalid_price", "n/a")
