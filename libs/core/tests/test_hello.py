"""Hello unit test module."""

from core.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello core"
