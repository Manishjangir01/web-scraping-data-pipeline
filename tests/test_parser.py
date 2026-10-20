from helpers import PAGE_1, build_page

from scrapepipe.parser import parse_listing

BASE = "http://shop.test/"


def test_listing_fields_are_extracted():
    html = build_page(PAGE_1, "catalogue/", "catalogue/page-2.html")
    records, next_url = parse_listing(html, BASE)

    assert len(records) == 5
    first = records[0]
    assert first["title"] == "A Light in the Attic"
    assert first["url"] == f"{BASE}catalogue/a-light-in-the-attic_1/index.html"
    assert first["price_text"] == "£51.77"
    assert first["rating_text"] == "Three"
    assert first["availability_text"] == "In stock"
    assert first["page_url"] == BASE
    assert next_url == f"{BASE}catalogue/page-2.html"


def test_next_link_is_resolved_relative_to_the_current_page():
    html = build_page(PAGE_1[:1], "", "page-3.html")
    _, next_url = parse_listing(html, f"{BASE}catalogue/page-2.html")
    assert next_url == f"{BASE}catalogue/page-3.html"


def test_last_page_has_no_next_link():
    _, next_url = parse_listing(build_page(PAGE_1[:1], "", None), BASE)
    assert next_url is None


def test_full_title_comes_from_the_title_attribute_not_the_shortened_text():
    records, _ = parse_listing(build_page(PAGE_1[4:5], "", None), BASE)
    assert records[0]["title"] == "Sapiens: A Brief History of Humankind"


def test_missing_price_becomes_none():
    records, _ = parse_listing(build_page([("No Price", None, "Two", "In stock")], "", None), BASE)
    assert records[0]["price_text"] is None


def test_page_without_books_gives_empty_list():
    assert parse_listing("<html><body><p>nothing here</p></body></html>", BASE) == ([], None)
