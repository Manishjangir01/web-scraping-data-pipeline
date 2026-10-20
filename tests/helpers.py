"""Build small HTML pages that copy the markup of books.toscrape.com, and serve them locally."""

from __future__ import annotations

import html
import re
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def book_html(title, href, price_text, rating_word, availability="In stock"):
    """One <article class="product_pod"> like the live site. price_text=None leaves the price out."""
    price = f'<p class="price_color">{price_text}</p>' if price_text is not None else ""
    safe_title = html.escape(title, quote=True)
    return f"""
<li class="col-xs-6 col-sm-4 col-md-3 col-lg-3">
<article class="product_pod">
    <div class="image_container">
        <a href="{href}"><img src="media/cache/x.jpg" alt="{safe_title}" class="thumbnail"></a>
    </div>
    <p class="star-rating {rating_word}">
        <i class="icon-star"></i><i class="icon-star"></i><i class="icon-star"></i><i class="icon-star"></i><i class="icon-star"></i>
    </p>
    <h3><a href="{href}" title="{safe_title}">{safe_title[:25]}</a></h3>
    <div class="product_price">
        {price}
        <p class="instock availability">
            <i class="icon-ok"></i>
            {availability}
        </p>
        <form><button type="submit" class="btn btn-primary btn-block">Add to basket</button></form>
    </div>
</article>
</li>"""


def page_html(books_html: str, next_href: str | None = None) -> str:
    nxt = f'<li class="next"><a href="{next_href}">next</a></li>' if next_href else ""
    return f"""<!DOCTYPE html>
<html lang="en-us">
<head><title>All products | Books to Scrape - Sandbox</title>
<meta http-equiv="content-type" content="text/html; charset=UTF-8" /></head>
<body><div class="container-fluid page"><div class="page_inner"><section>
<ol class="row">{books_html}</ol>
<div><ul class="pager">{nxt}<li class="current">Page</li></ul></div>
</section></div></div></body></html>"""


# (title, price text, rating word, availability). Page 1 links look like "catalogue/<slug>_<n>/index.html",
# pages 2 and 3 live in /catalogue/ and link like "<slug>_<n>/index.html", as on the real site.
PAGE_1 = [
    ("A Light in the Attic", "£51.77", "Three", "In stock"),
    ("Tipping the Velvet", "£53.74", "One", "In stock"),
    ("Soumission", "£50.10", "One", "In stock"),
    ("Sharp Objects", "£47.82", "Four", "In stock"),
    ("Sapiens: A Brief History of Humankind", "£54.23", "Five", "In stock"),
]
PAGE_2 = [
    ("The Requiem Red", "£22.65", "One", "In stock"),
    ("The Dirty Little Secrets of Getting Your Dream Job", "£33.34", "Four", "In stock"),
    ("The Coming Woman", "£17.93", "Three", "Out of stock"),
    ("Sharp Objects", "£47.82", "Four", "In stock"),  # same book as on page 1 -> duplicate_url
    ("Starving Hearts", "£13.99", "Two", "In stock"),
]
PAGE_3 = [
    ("Scott Pilgrim's Precious Little Life", "Â£52.29", "Five", "In stock"),  # wrongly decoded £
    ("Rip it Up and Start Again", None, "Five", "In stock"),  # no price -> invalid_price
    ("Mesaerion: The Best Science Fiction Stories", "£37.59", "Zero", "In stock"),  # -> invalid_rating
    ("Olio", "£23.88", "One", "In stock"),
]

BOOK_NUMBERS = {}  # title -> number, so the same title always gets the same URL


def _href(title: str, prefix: str) -> str:
    number = BOOK_NUMBERS.setdefault(title, len(BOOK_NUMBERS) + 1)
    return f"{prefix}{slug(title)}_{number}/index.html"


def build_page(books, prefix: str, next_href: str | None) -> str:
    return page_html("".join(book_html(t, _href(t, prefix), p, r, a) for t, p, r, a in books), next_href)


class Site:
    """A throw-away web server on 127.0.0.1 that serves our pages and records requests."""

    def __init__(self):
        self.pages: dict[str, str] = {}
        self.robots: str | None = "User-agent: *\nAllow: /\n"
        self.hits: Counter = Counter()
        self.fail_next: dict[str, int] = {}  # path -> how many 503 answers to give before working
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> "Site":
        site = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, status: int, body: bytes = b"", content_type: str = "text/html"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)  # no charset, like the real site
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urlsplit(self.path).path
                site.hits[path] += 1
                if site.fail_next.get(path, 0) > 0:
                    site.fail_next[path] -= 1
                    return self._send(503)
                if path == "/robots.txt":
                    if site.robots is None:
                        return self._send(404)
                    return self._send(200, site.robots.encode(), "text/plain")
                page = site.pages.get(path)
                if page is None:
                    return self._send(404)
                return self._send(200, page.encode("utf-8"))

            def log_message(self, *args):  # keep test output quiet
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/"

    def load_default_pages(self) -> None:
        self.pages = {
            "/": build_page(PAGE_1, "catalogue/", "catalogue/page-2.html"),
            "/catalogue/page-2.html": build_page(PAGE_2, "", "page-3.html"),
            "/catalogue/page-3.html": build_page(PAGE_3, "", None),
        }
