import pytest

from scrapepipe.fetcher import DisallowedByRobots, FetchError, Fetcher, build_session

PAGE2 = "/catalogue/page-2.html"


def make_fetcher(retries=3, **kwargs):
    """Real HTTP requests to the local test server, with no waiting between retries."""
    kwargs.setdefault("delay", 0)
    return Fetcher(session=build_session(retries=retries, backoff=0), **kwargs)


def test_page_text_is_returned(site):
    text = make_fetcher().get(site.base_url)
    assert "A Light in the Attic" in text


def test_pound_sign_is_decoded_correctly_when_the_server_sends_no_charset(site):
    text = make_fetcher().get(site.base_url)
    assert "£51.77" in text
    assert "Â£" not in text


def test_temporary_503_errors_are_retried(site):
    site.fail_next[PAGE2] = 2
    text = make_fetcher(retries=3).get(site.base_url + "catalogue/page-2.html")
    assert "The Requiem Red" in text
    assert site.hits[PAGE2] == 3  # two failures and then the success


def test_gives_up_after_the_retries_and_raises_fetch_error(site):
    site.fail_next[PAGE2] = 99
    with pytest.raises(FetchError):
        make_fetcher(retries=2).get(site.base_url + "catalogue/page-2.html")
    assert site.hits[PAGE2] == 3  # first try and two retries


def test_404_is_an_error_and_is_not_retried(site):
    with pytest.raises(FetchError):
        make_fetcher().get(site.base_url + "catalogue/missing.html")
    assert site.hits["/catalogue/missing.html"] == 1


def test_robots_txt_disallow_blocks_the_request(site):
    site.robots = "User-agent: *\nDisallow: /catalogue/\n"
    fetcher = make_fetcher()
    assert "A Light in the Attic" in fetcher.get(site.base_url)  # "/" is still allowed
    with pytest.raises(DisallowedByRobots):
        fetcher.get(site.base_url + "catalogue/page-2.html")
    assert site.hits[PAGE2] == 0  # the page was never requested


def test_missing_robots_txt_means_everything_is_allowed(site):
    site.robots = None
    assert "A Light in the Attic" in make_fetcher().get(site.base_url)


def test_unreachable_robots_txt_means_nothing_is_fetched(site):
    site.fail_next["/robots.txt"] = 99
    with pytest.raises(DisallowedByRobots):
        make_fetcher(retries=1).get(site.base_url)
    assert site.hits["/"] == 0


def test_robots_txt_is_downloaded_only_once(site):
    fetcher = make_fetcher()
    fetcher.get(site.base_url)
    fetcher.get(site.base_url + "catalogue/page-2.html")
    assert site.hits["/robots.txt"] == 1


def test_polite_delay_between_requests(site):
    sleeps = []
    fetcher = make_fetcher(delay=1.0, sleep=sleeps.append, clock=lambda: 100.0)  # clock never moves
    fetcher.get(site.base_url)  # first request: no wait
    fetcher.get(site.base_url + "catalogue/page-2.html")
    fetcher.get(site.base_url + "catalogue/page-3.html")
    assert sleeps == [1.0, 1.0]


def test_no_wait_when_enough_time_has_passed(site):
    sleeps = []
    ticks = iter([0.0, 5.0, 10.0, 15.0, 20.0])
    fetcher = make_fetcher(delay=1.0, sleep=sleeps.append, clock=lambda: next(ticks))
    fetcher.get(site.base_url)
    fetcher.get(site.base_url + "catalogue/page-2.html")
    assert sleeps == []
