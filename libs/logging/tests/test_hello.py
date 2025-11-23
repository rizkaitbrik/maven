"""Hello unit test module."""

from logging.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello logging"
