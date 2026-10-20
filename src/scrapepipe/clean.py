"""Clean and validate raw records."""

from __future__ import annotations

import re

from scrapepipe import config

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

REJECT_REASONS = (
    "missing_title",
    "missing_url",
    "invalid_price",
    "invalid_rating",
    "duplicate_url",
)


def parse_price(text: str | None) -> float | None:
    """"£51.77" -> 51.77. Also copes with "Â£51.77" (wrongly decoded) and "£1,051.77"."""
    if not text:
        return None
    match = _NUMBER.search(text.replace(",", ""))
    return float(match.group()) if match else None


def clean_records(records: list[dict], scraped_at: str) -> tuple[list[dict], list[dict]]:
    """Return ``(clean, rejected)``.

    A record is rejected for the first rule it breaks (see ``REJECT_REASONS``).
    When the same URL appears twice, the first copy is kept.
    """
    clean: list[dict] = []
    rejected: list[dict] = []
    seen: set[str] = set()

    for rec in records:
        title = " ".join((rec.get("title") or "").split())
        url = (rec.get("url") or "").strip()
        price = parse_price(rec.get("price_text"))
        rating = config.RATING_WORDS.get(rec.get("rating_text") or "")

        if not title:
            reason = "missing_title"
        elif not url.startswith(("http://", "https://")):
            reason = "missing_url"
        elif price is None or not 0 < price <= config.MAX_PRICE:
            reason = "invalid_price"
        elif rating is None:
            reason = "invalid_rating"
        elif url in seen:
            reason = "duplicate_url"
        else:
            reason = None

        if reason:
            rejected.append({**rec, "reject_reason": reason, "scraped_at": scraped_at})
            continue

        seen.add(url)
        availability = (rec.get("availability_text") or "").lower()
        clean.append(
            {
                "title": title,
                "url": url,
                "price": price,
                "rating": rating,
                "in_stock": "in stock" in availability,
                "page_url": rec.get("page_url"),
                "scraped_at": scraped_at,
            }
        )
    return clean, rejected
