"""Turn a listing page into raw records. No cleaning happens here."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_listing(html: str, page_url: str) -> tuple[list[dict], str | None]:
    """Return ``(records, next_page_url)``.

    Every value is kept as the page shows it (price as text like "£51.77",
    rating as a word like "Three"). Missing elements become None, and the
    cleaning step decides what to do about them.
    """
    soup = BeautifulSoup(html, "lxml")
    records = []
    for pod in soup.select("article.product_pod"):
        link = pod.select_one("h3 a")
        price = pod.select_one("p.price_color")
        rating = pod.select_one("p.star-rating")
        availability = pod.select_one("p.availability")

        title = None
        url = None
        if link is not None:
            title = link.get("title") or link.get_text(strip=True)
            if link.get("href"):
                url = urljoin(page_url, link["href"])

        rating_text = None
        if rating is not None:
            rating_text = next((c for c in rating.get("class", []) if c != "star-rating"), None)

        records.append(
            {
                "title": title,
                "url": url,
                "price_text": price.get_text(strip=True) if price is not None else None,
                "rating_text": rating_text,
                "availability_text": (
                    " ".join(availability.get_text().split()) if availability is not None else None
                ),
                "page_url": page_url,
            }
        )

    next_link = soup.select_one("li.next a")
    next_url = None
    if next_link is not None and next_link.get("href"):
        next_url = urljoin(page_url, next_link["href"])
    return records, next_url
