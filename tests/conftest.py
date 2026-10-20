import pytest

from helpers import Site


@pytest.fixture
def site():
    """A local web server holding three listing pages (14 books, 3 of them bad or repeated)."""
    s = Site().start()
    s.load_default_pages()
    yield s
    s.stop()
