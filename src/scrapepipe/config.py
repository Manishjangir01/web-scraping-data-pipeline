"""Settings in one place."""

# books.toscrape.com is a practice site that exists to be scraped.
BASE_URL = "https://books.toscrape.com/"

USER_AGENT = (
    "scrapepipe/0.1 (portfolio project; "
    "https://github.com/Manishjangir01/web-scraping-data-pipeline)"
)

REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3  # extra attempts after the first one
BACKOFF_FACTOR = 0.5  # waits 0.5s, 1s, 2s ... between retries
DEFAULT_DELAY = 1.0  # seconds to wait between page requests

# The site writes star ratings as a CSS class, e.g. <p class="star-rating Three">.
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

MAX_PRICE = 10_000.0  # anything above this is treated as a parsing error
