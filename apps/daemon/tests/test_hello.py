"""Hello unit test module."""

from daemon.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello daemon"
