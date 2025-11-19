"""Hello unit test module."""

from retrieval.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello retrieval"
