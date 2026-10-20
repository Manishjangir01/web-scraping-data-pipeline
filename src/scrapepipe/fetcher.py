"""HTTP layer: retries with backoff, a polite delay between requests and robots.txt."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scrapepipe import config

log = logging.getLogger("scrapepipe")


class FetchError(Exception):
    """A page could not be downloaded."""


class DisallowedByRobots(FetchError):
    """robots.txt does not allow this URL."""


def build_session(
    user_agent: str = config.USER_AGENT,
    retries: int = config.MAX_RETRIES,
    backoff: float = config.BACKOFF_FACTOR,
) -> requests.Session:
    """A session that retries timeouts, connection errors and 429/5xx responses."""
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = user_agent
    return session


class Fetcher:
    """Downloads pages one at a time, politely.

    - waits ``delay`` seconds between requests,
    - checks robots.txt once per site and refuses disallowed URLs,
    - raises ``FetchError`` when a page still fails after the retries.
    """

    def __init__(
        self,
        session: requests.Session | None = None,
        delay: float = config.DEFAULT_DELAY,
        timeout: float = config.REQUEST_TIMEOUT,
        respect_robots: bool = True,
        user_agent: str = config.USER_AGENT,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.session = session or build_session(user_agent)
        self.delay = delay
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.user_agent = user_agent
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self._robots: dict[str, RobotFileParser] = {}

    # -- robots.txt ---------------------------------------------------------
    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(origin)
        if parser is None:
            parser = RobotFileParser()
            try:
                resp = self.session.get(f"{origin}/robots.txt", timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning("robots.txt unreachable (%s), so nothing will be fetched", exc)
                parser.disallow_all = True
            else:
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                elif 400 <= resp.status_code < 500:
                    parser.allow_all = True  # no robots.txt means no restrictions
                else:
                    parser.disallow_all = True
            self._robots[origin] = parser
        return parser

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        return self._robots_for(url).can_fetch(self.user_agent, url)

    # -- downloading --------------------------------------------------------
    def _wait(self) -> None:
        if self._last_request is None:
            return
        remaining = self.delay - (self._clock() - self._last_request)
        if remaining > 0:
            self._sleep(remaining)

    def get(self, url: str) -> str:
        """Return the page text, or raise FetchError."""
        if not self.allowed(url):
            raise DisallowedByRobots(f"robots.txt does not allow {url}")
        self._wait()
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise FetchError(f"GET {url} failed: {exc}") from exc
        finally:
            self._last_request = self._clock()
        # Some servers send HTML without a charset. requests then guesses ISO-8859-1
        # and turns "£" into "Â£". These pages are UTF-8.
        if "charset" not in resp.headers.get("Content-Type", "").lower():
            resp.encoding = "utf-8"
        log.info("fetched %s (%s bytes)", url, len(resp.content))
        return resp.text
