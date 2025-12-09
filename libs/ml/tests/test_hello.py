"""Hello unit test module."""

from ml.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello ml"
