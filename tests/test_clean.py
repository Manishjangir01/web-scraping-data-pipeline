from scrapepipe.clean import clean_records, parse_price

TS = "2026-01-01T00:00:00+00:00"


def rec(**overrides):
    base = {
        "title": "A Book",
        "url": "http://shop.test/a-book_1/index.html",
        "price_text": "£10.00",
        "rating_text": "Three",
        "availability_text": "In stock",
        "page_url": "http://shop.test/",
    }
    base.update(overrides)
    return base


def test_parse_price_variants():
    assert parse_price("£51.77") == 51.77
    assert parse_price("Â£51.77") == 51.77  # £ decoded with the wrong charset
    assert parse_price("£1,051.77") == 1051.77
    assert parse_price("20") == 20.0
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("free") is None


def test_valid_record_is_typed_and_cleaned():
    clean, rejected = clean_records([rec(title="  Two   spaces  ", rating_text="Five")], TS)
    assert rejected == []
    assert clean == [
        {
            "title": "Two spaces",
            "url": "http://shop.test/a-book_1/index.html",
            "price": 10.0,
            "rating": 5,
            "in_stock": True,
            "page_url": "http://shop.test/",
            "scraped_at": TS,
        }
    ]


def test_out_of_stock_and_unknown_availability():
    clean, _ = clean_records(
        [
            rec(url="http://shop.test/1", availability_text="Out of stock"),
            rec(url="http://shop.test/2", availability_text=None),
        ],
        TS,
    )
    assert [c["in_stock"] for c in clean] == [False, False]


def test_each_rule_gives_its_own_reason():
    records = [
        rec(title=""),
        rec(url=None),
        rec(price_text=None, url="http://shop.test/3"),
        rec(price_text="£0.00", url="http://shop.test/4"),
        rec(price_text="£999999", url="http://shop.test/5"),
        rec(rating_text="Zero", url="http://shop.test/6"),
        rec(rating_text=None, url="http://shop.test/7"),
    ]
    clean, rejected = clean_records(records, TS)
    assert clean == []
    assert [r["reject_reason"] for r in rejected] == [
        "missing_title",
        "missing_url",
        "invalid_price",
        "invalid_price",
        "invalid_price",
        "invalid_rating",
        "invalid_rating",
    ]
    assert all(r["scraped_at"] == TS for r in rejected)


def test_duplicate_url_keeps_the_first_copy():
    clean, rejected = clean_records(
        [rec(price_text="£10.00"), rec(price_text="£99.00")],  # same url
        TS,
    )
    assert [c["price"] for c in clean] == [10.0]
    assert [r["reject_reason"] for r in rejected] == ["duplicate_url"]


def test_rejected_rows_keep_the_raw_values():
    _, rejected = clean_records([rec(price_text="n/a")], TS)
    assert rejected[0]["price_text"] == "n/a"
    assert rejected[0]["title"] == "A Book"
